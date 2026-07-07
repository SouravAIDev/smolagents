-- Mark books as displayed in session context (Flow B state update)
-- Updates the is_displayed flag after user views pagination results
UPDATE {context_table}
SET
    is_displayed = TRUE,
    updated_at = CURRENT_TIMESTAMP
WHERE
    session_id = %s::uuid
    AND book_id IN (%s)
RETURNING session_id, book_id, is_displayed;