-- Vector similarity search with optional multi-table join support for book metadata
-- Parameters: query_vector, similarity_threshold, limit
-- Format placeholders: select_columns, table_name, search_column, return_column
-- Optional: normalized_join_path, normalized_pk, normalized_fk (for 1:N relationships)

SELECT DISTINCT
    {select_columns},
    {return_column},
    (1 - (t.{search_column} <=> %s::vector)) AS similarity_score
FROM {table_name} t
WHERE t.{search_column} IS NOT NULL
  AND (1 - (t.{search_column} <=> %s::vector)) >= %s
ORDER BY similarity_score DESC, {return_column} ASC
LIMIT %s;