-- Mark books as displayed and increment display count
-- Batch update using VALUES clause for efficiency
-- Parameters: List of (isbn, increment_count) pairs, followed by session_id and question
-- Format placeholder: table_name, value_clauses

UPDATE {table_name} AS t
SET
    is_displayed = TRUE,
    display_count = display_count + v.increment_count,
    updated_at = CURRENT_TIMESTAMP
FROM (VALUES {value_clauses}) AS v(isbn, increment_count)
WHERE t.isbn = v.isbn
    AND t.session_id = %s
    AND t.question = %s
    AND t.is_expired = FALSE;