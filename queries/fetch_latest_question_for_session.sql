-- Fetch the most recent question for a session (Flow C support)
-- Used to reconstruct context when applying new filters to previous queries
SELECT
    question,
    MAX(created_at) as latest_timestamp
FROM
    {context_table}
WHERE
    session_id = %s::uuid
GROUP BY
    question
ORDER BY
    latest_timestamp DESC
LIMIT 1;