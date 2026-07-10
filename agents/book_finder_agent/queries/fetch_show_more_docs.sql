-- Retrieve both displayed and undisplayed documents for pagination (Flow B: Show More)
-- Fetches previously shown results and the next batch of undisplayed results
-- Results are already ranked and scored from the previous retrieval

WITH
    undisplayed AS (
        SELECT
            book_id,
            book_title,
            authors,
            genres,
            isbn,
            publication_date,
            summary,
            publisher,
            audience,
            relevance_score,
            embedding_similarity,
            filter_match_count,
            keyword_boost,
            supporting_excerpts,
            metadata,
            created_at,
            updated_at,
            id
        FROM book_finder_chat_data
        WHERE
            session_id = % s
            AND question_id = % s
            AND is_displayed = FALSE
        ORDER BY relevance_score DESC
        LIMIT % s
    )
SELECT combined.*, total.total_count
FROM (
        SELECT *, TRUE AS is_displayed
        FROM book_finder_chat_data
        WHERE
            session_id = % s
            AND question_id = % s
            AND is_displayed = TRUE
        UNION ALL
        SELECT *, FALSE AS is_displayed
        FROM undisplayed
    ) combined
    CROSS JOIN (
        SELECT COUNT(*) AS total_count
        FROM book_finder_chat_data
        WHERE
            session_id = % s
            AND question_id = % s
    ) total
ORDER BY relevance_score DESC
LIMIT % s;