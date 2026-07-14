-- Exact-match filter query for book metadata (non-vector searches)
-- Supports hard filters on categorical fields (genre, publisher, etc.)
-- Parameters: search_value, limit
-- Format placeholders: select_columns, table_name, search_column, return_column, condition_operator

SELECT
    {select_columns},
    {return_column},
    1.0 AS relevance_score
FROM {table_name}
WHERE {search_column} {condition_operator} %s
ORDER BY {return_column} ASC
LIMIT %s;