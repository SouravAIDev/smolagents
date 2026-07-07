-- Vector similarity search with table joins for complex filter types
-- Executes semantic search across related tables (authors, genres, excerpts) with normalization
SELECT
    bm.book_id,
    1 - ({embedding_column} <=> %s::vector) AS similarity_score,
    bm.* EXCEPT ({embedding_column})
FROM
    {source_table} st
{joins}
WHERE
    1 - (st.{embedding_column} <=> %s::vector) >= %s
ORDER BY
    st.{embedding_column} <=> %s::vector
LIMIT %s;