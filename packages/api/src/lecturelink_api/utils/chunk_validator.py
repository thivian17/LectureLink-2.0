def validate_chunk_references(supabase, chunk_ids: list[str]) -> dict:
    """Validate that chunk IDs still exist in the database.

    Returns dict with valid_ids and has_orphans flag.
    Used by quiz results and Q&A citation display to handle
    cases where lecture reprocessing deleted referenced chunks.
    """
    if not chunk_ids:
        return {'valid_ids': [], 'has_orphans': False}

    result = supabase.table('lecture_chunks') \
        .select('id') \
        .in_('id', chunk_ids) \
        .execute()
    
    valid_ids = [r['id'] for r in result.data]
    return {
        'valid_ids': valid_ids,
        'has_orphans': len(valid_ids) < len(chunk_ids),
    }