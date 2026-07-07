-- Fallback query for fetching show-more documents when session context unavailable
-- Directly queries book metadata table for highest-scoring undisplayed books
SELECT
    bm.book_id,
    bm.title,
    bm.author_name,
    bm.isbn,
    bm.genre,
    bm.summary,
    bm.publication_date,
    COALESCE(be.excerpt_text, bm.summary) as excerpt,
    1 - ({embedding_column} <=> %s::vector) AS similarity_score
FROM
    {book_table} bm
LEFT JOIN
    {excerpt_table} be ON bm.book_id = be.book_id
WHERE
    bm.book_id IN (%s)
ORDER BY
    similarity_score DESC,
    bm.book_id
LIMIT %s;