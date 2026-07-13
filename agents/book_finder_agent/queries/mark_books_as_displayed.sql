-- Mark books as displayed after being shown to the LLM
-- Updates is_displayed flag and tracks which results were used for generation
-- Used by pagination flow to prevent duplicate results in subsequent requests

UPDATE book_finder_chat_data
SET
    is_displayed = TRUE,
    updated_at = CURRENT_TIMESTAMP
WHERE
    session_id = % s
    AND question_id = % s
    AND book_id = ANY (% s) RETURNING book_id,
    is_displayed,
    updated_at;