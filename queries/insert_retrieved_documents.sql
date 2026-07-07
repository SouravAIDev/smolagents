-- Insert newly retrieved documents into session context table
-- Stores book data for pagination and filtering workflows
INSERT INTO {context_table} (
    session_id,
    book_id,
    question,
    book_data,
    is_displayed,
    similarity_score,
    created_at
) VALUES
    (%s, %s, %s, %s::jsonb, FALSE, %s, CURRENT_TIMESTAMP)
ON CONFLICT (session_id, book_id) DO UPDATE
SET
    book_data = EXCLUDED.book_data,
    is_displayed = EXCLUDED.is_displayed,
    similarity_score = EXCLUDED.similarity_score,
    updated_at = CURRENT_TIMESTAMP;