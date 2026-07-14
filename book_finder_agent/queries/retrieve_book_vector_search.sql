-- Retrieve books by semantic similarity to user query
-- Uses pgvector cosine distance operator for efficient HNSW index utilization
-- Parameters: query_vector (VECTOR(1536)), distance_threshold (float), limit (int)
-- Format placeholders: select_columns, table_name, search_column, return_column, limit

SELECT
    {select_columns},
    1 - ({search_column} <=> %s::vector) AS similarity_score,
    {search_column} <=> %s::vector AS distance
FROM {table_name}
WHERE {search_column} <=> %s::vector <= %s
ORDER BY {search_column} <=> %s::vector ASC
LIMIT %s;