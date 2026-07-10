-- Fetch the most recent question for a given session
-- Used to enable filtered context retrieval (Flow C) when user applies filters
-- to existing session results.
--
-- Query: Retrieves the latest user_query asked in a specific session,
-- ordered by created_at DESC to get the most recent question.
--
-- Parameters:
--   session_id (UUID): The session identifier to filter results
--
-- Returns:
--   - question_id: UUID of the question record
--   - user_query: The text of the most recent user query
--   - created_at: Timestamp when the question was asked

SELECT
    question_id,
    user_query,
    created_at
FROM book_finder_chat_data
WHERE
    session_id = % s
ORDER BY created_at DESC
LIMIT 1;