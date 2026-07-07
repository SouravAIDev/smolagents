-- Fetch documents filtered by JSONB metadata (Flow C - pre-filtered questions)
-- Applies structured filter criteria to previously retrieved session documents
SELECT
    book_id,
    book_data,
    similarity_score
FROM
    {context_table}
WHERE
    session_id = %s::uuid
    {filter_conditions}
ORDER BY
    similarity_score DESC,
    created_at ASC
LIMIT %s;