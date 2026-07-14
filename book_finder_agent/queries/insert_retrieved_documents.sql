-- Insert newly retrieved books into session context table
-- Batch insert using multi-row VALUES for efficiency
-- Parameters: List of (session_id, isbn, context_score, is_displayed, is_expired, display_count, chunk_ids) tuples
-- Format placeholder: table_name, values_clause

INSERT INTO {table_name}
    (session_id, isbn, context_score, is_displayed, is_expired, display_count, chunk_ids, created_at, updated_at)
VALUES {values_clause}
ON CONFLICT DO NOTHING;