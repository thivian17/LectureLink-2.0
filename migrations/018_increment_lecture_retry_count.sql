-- -------------------------------------------------------
-- Increment RPC for lecture retry (mirrors increment_material_retry_count)
-- -------------------------------------------------------
CREATE OR REPLACE FUNCTION increment_lecture_retry_count(p_lecture_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE lectures
    SET retry_count = retry_count + 1,
        updated_at = now()
    WHERE id = p_lecture_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
