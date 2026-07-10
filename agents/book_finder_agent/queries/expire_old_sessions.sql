-- Delete expired session records from the chat data table
-- Called periodically or before inserting new session data to maintain storage efficiency
-- Removes all records where expires_at timestamp has passed

DELETE FROM book_finder_chat_data
WHERE
    expires_at IS NOT NULL
    AND expires_at < CURRENT_TIMESTAMP RETURNING session_id,
    question_id,
    COUNT(*) as deleted_count;