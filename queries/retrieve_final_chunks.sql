-- Retrieve final book excerpts/chunks for LLM context enrichment
-- Fetches supporting excerpts for selected books after scoring and filtering
SELECT
    be.book_id,
    be.excerpt_id,
    be.excerpt_text,
    be.excerpt_location,
    be.chapter_number,
    1 - (be.excerpt_embeddings <=> %s::vector) AS chunk_similarity_score
FROM
    {excerpt_table} be
WHERE
    be.book_id = ANY(%s::uuid[])
    AND 1 - (be.excerpt_embeddings <=> %s::vector) >= %s
ORDER BY
    be.book_id,
    1 - (be.excerpt_embeddings <=> %s::vector) DESC
LIMIT %s;