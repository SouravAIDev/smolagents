-- DEPRECATED: This file is contract-specific and should not be used with BookFinderAgent.
-- Use retrieve_book_vector_search.sql instead for semantic similarity searches.
SELECT
    {select_columns},
    {return_column},
    1 - ({search_column} <=> %s::vector) AS similarity_score,
    {search_column} <=> %s::vector AS distance
FROM {table_name}
WHERE {search_column} <=> %s::vector <= %s
ORDER BY {search_column} <=> %s::vector ASC
LIMIT %s;