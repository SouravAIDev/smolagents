-- Fetch undisplayed documents from session context for pagination (Flow B)
-- Returns books not yet shown to user, ordered by relevance score
SELECT
    book_id,
    book_data,
    similarity_score
FROM
    {context_table}
WHERE
    session_id = %s::uuid
    AND is_displayed = FALSE
ORDER BY
    similarity_score DESC,
    created_at ASC
LIMIT %s;