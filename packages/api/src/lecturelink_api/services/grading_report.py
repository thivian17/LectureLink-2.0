"""
Grading feedback aggregate report.

Analyzes the grading_feedback table to surface where the tutor grader
is systematically wrong. Used by the internal /grading-feedback-report endpoint.

Key signal: inaccuracy_rate by question_type and concept category.
When inaccuracy > 20% for a category, flag it for prompt review.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

INACCURACY_ALERT_THRESHOLD = 0.20  # flag if >20% of gradings marked inaccurate


async def get_grading_feedback_report(
    supabase,
    lookback_days: int = 30,
) -> dict:
    """
    Generate grading accuracy report across all users.

    Returns:
        {
            "period_days": 30,
            "total_feedback": 87,
            "overall_inaccuracy_rate": 0.12,
            "by_question_type": [
                {"question_type": "short_answer", "total": 400, "inaccurate": 62,
                 "inaccuracy_rate": 0.155, "flagged": false},
                ...
            ],
            "flagged_types": ["short_answer"],
            "sample_inaccurate_gradings": [...]
        }
    """
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    try:
        # Get all grading feedback in the period
        feedback_result = (
            supabase.table("grading_feedback")
            .select(
                "id, feedback_type, feedback_text, created_at, "
                "tutor_session_events (question_type, misconception_type, "
                "grading_result, concept_title)"
            )
            .gte("created_at", since)
            .execute()
        )
        feedback_rows = feedback_result.data or []

        total_feedback = len(feedback_rows)
        inaccurate_rows = [
            r for r in feedback_rows if r.get("feedback_type") == "inaccurate"
        ]

        # Aggregate by question type
        by_type: dict[str, dict] = {}
        for row in feedback_rows:
            event = row.get("tutor_session_events") or {}
            qtype = event.get("question_type", "unknown")
            if qtype not in by_type:
                by_type[qtype] = {"total": 0, "inaccurate": 0}
            by_type[qtype]["total"] += 1
            if row.get("feedback_type") == "inaccurate":
                by_type[qtype]["inaccurate"] += 1

        by_type_list = []
        flagged_types = []
        for qtype, counts in sorted(by_type.items(), key=lambda x: -x[1]["inaccurate"]):
            rate = counts["inaccurate"] / counts["total"] if counts["total"] > 0 else 0.0
            flagged = rate >= INACCURACY_ALERT_THRESHOLD and counts["total"] >= 10
            if flagged:
                flagged_types.append(qtype)
            by_type_list.append({
                "question_type": qtype,
                "total": counts["total"],
                "inaccurate": counts["inaccurate"],
                "inaccuracy_rate": round(rate, 3),
                "flagged": flagged,
            })

        # Sample of recent inaccurate gradings for manual review
        samples = [
            {
                "feedback_text": r.get("feedback_text"),
                "question_type": (r.get("tutor_session_events") or {}).get(
                    "question_type"
                ),
                "concept": (r.get("tutor_session_events") or {}).get("concept_title"),
                "created_at": r.get("created_at"),
            }
            for r in sorted(
                inaccurate_rows,
                key=lambda x: x.get("created_at", ""),
                reverse=True,
            )[:10]
        ]

        overall_rate = (
            len(inaccurate_rows) / total_feedback if total_feedback > 0 else 0.0
        )

        return {
            "period_days": lookback_days,
            "total_feedback": total_feedback,
            "overall_inaccuracy_rate": round(overall_rate, 3),
            "by_question_type": by_type_list,
            "flagged_types": flagged_types,
            "sample_inaccurate_gradings": samples,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Failed to generate grading feedback report: %s", e)
        return {"error": str(e)}
