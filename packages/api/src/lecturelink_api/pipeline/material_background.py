"""Background task runner for material processing with retry logic.

Provides both sync (thread-based) and async entry points:
- ``run_material_processing`` — sync, for thread-pool fallback
- ``run_material_processing_async`` — async, called by arq workers
"""

from __future__ import annotations

import asyncio
import logging

from supabase import create_client

from ..services.material_storage import update_material_status
from .material_processor import MaterialProcessingError, process_material

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def run_material_processing_async(
    supabase_url: str,
    supabase_key: str,
    user_token: str,
    material_id: str,
    course_id: str,
    user_id: str,
    file_url: str,
    file_name: str,
    material_type: str,
    title: str | None = None,
    is_reprocess: bool = False,
) -> dict | None:
    """Async entry point for material processing (used by arq worker)."""
    sb = create_client(supabase_url, supabase_key)
    if user_token:
        sb.auth.set_session(user_token, "")

    return await _processing_loop(
        sb,
        material_id,
        course_id,
        user_id,
        file_url,
        file_name,
        material_type,
        title,
        is_reprocess,
    )


def run_material_processing(
    supabase_url: str,
    supabase_key: str,
    user_token: str,
    material_id: str,
    course_id: str,
    user_id: str,
    file_url: str,
    file_name: str,
    material_type: str,
    title: str | None = None,
    is_reprocess: bool = False,
) -> dict | None:
    """Sync fallback for material processing (daemon thread)."""
    loop = asyncio.new_event_loop()
    try:
        sb = create_client(supabase_url, supabase_key)
        if user_token:
            sb.auth.set_session(user_token, "")
        return loop.run_until_complete(
            _processing_loop(
                sb,
                material_id,
                course_id,
                user_id,
                file_url,
                file_name,
                material_type,
                title,
                is_reprocess,
            )
        )
    except Exception:
        logger.exception("Material %s: daemon thread crashed", material_id)
        try:
            sb2 = create_client(supabase_url, supabase_key)
            update_material_status(
                sb2, material_id, "failed", error="Processing thread crashed"
            )
        except Exception:
            pass
        return None
    finally:
        loop.close()


async def _processing_loop(
    supabase,
    material_id: str,
    course_id: str,
    user_id: str,
    file_url: str,
    file_name: str,
    material_type: str,
    title: str | None,
    is_reprocess: bool,
) -> dict | None:
    """Core processing loop with retry logic."""
    try:
        result = await process_material(
            supabase=supabase,
            material_id=material_id,
            course_id=course_id,
            user_id=user_id,
            file_url=file_url,
            file_name=file_name,
            material_type=material_type,
            title=title,
            is_reprocess=is_reprocess,
        )
        return result

    except MaterialProcessingError as e:
        logger.error(
            "Material %s failed at stage '%s': %s", material_id, e.stage, e
        )
        update_material_status(
            supabase,
            material_id,
            "failed",
            stage=e.stage,
            error=str(e),
        )
        # Increment retry count
        try:
            supabase.rpc(
                "increment_material_retry_count",
                {"p_material_id": material_id},
            ).execute()
        except Exception:
            logger.warning(
                "Failed to increment retry count for %s", material_id
            )
        return None

    except Exception as e:
        logger.exception("Material %s: unexpected error", material_id)
        update_material_status(
            supabase,
            material_id,
            "failed",
            error=f"Unexpected error: {e}",
        )
        return None
