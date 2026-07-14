-- Retrieves the most recent question asked within a specific session.
-- Used by Flow C (filtered question) to look up the original query before
-- applying additional filter constraints.

SELECT DISTINCT question
FROM {context_table}
WHERE session_id = %s
  AND is_expired = FALSE
ORDER BY id DESC
LIMIT 1;