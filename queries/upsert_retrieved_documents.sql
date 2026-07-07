-- UPSERT retrieved documents with session expiration
-- Expires old session context records and inserts/updates new ones
DELETE FROM {context_table}
WHERE
    session_id = %s::uuid
    AND created_at < CURRENT_TIMESTAMP - INTERVAL '%s';

INSERT INTO {context_table} (
    session_id,
    book_id,
    question,
    book_data,
    is_displayed,
    similarity_score,
    created_at
) VALUES
    (%s::uuid, %s::uuid, %s, %s::jsonb, FALSE, %s, CURRENT_TIMESTAMP)
ON CONFLICT (session_id, book_id) DO UPDATE
SET
    book_data = EXCLUDED.book_data,
    is_displayed = EXCLUDED.is_displayed,
    similarity_score = EXCLUDED.similarity_score,
    updated_at = CURRENT_TIMESTAMP
RETURNING session_id, book_id, similarity_score;