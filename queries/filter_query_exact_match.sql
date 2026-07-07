-- Exact match filtering query for hard filter types
-- Retrieves books matching specific attribute values without similarity thresholding
SELECT
    book_id,
    {select_columns}
FROM
    {table_name}
WHERE
    {filter_column} = %s
    AND book_id = ANY(%s::uuid[])
ORDER BY
    book_id
LIMIT %s;