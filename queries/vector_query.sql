-- Vector similarity search query for book retrieval
-- Executes pgvector cosine similarity search against embeddings
SELECT
    book_id,
    1 - ({embedding_column} <=> %s::vector) AS similarity_score,
    * EXCEPT ({embedding_column})
FROM
    {table_name}
WHERE
    1 - ({embedding_column} <=> %s::vector) >= %s
ORDER BY
    {embedding_column} <=> %s::vector
LIMIT %s;