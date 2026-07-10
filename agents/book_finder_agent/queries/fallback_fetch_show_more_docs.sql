-- Fallback pagination query: uses the latest question for the session if the provided question doesn't match
-- This handles cases where the user's question parameter differs from what was originally stored
-- Retrieves both displayed and undisplayed documents for the latest question in the session

WITH
    latest_question AS (
        SELECT user_query
        FROM book_finder_chat_data
        WHERE
            session_id = % s
        ORDER BY created_at DESC
        LIMIT 1
    ),
    undisplayed AS (
        SELECT
            bfd.book_id,
            bfd.book_title,
            bfd.authors,
            bfd.genres,
            bfd.isbn,
            bfd.publication_date,
            bfd.summary,
            bfd.publisher,
            bfd.audience,
            bfd.relevance_score,
            bfd.embedding_similarity,
            bfd.filter_match_count,
            bfd.keyword_boost,
            bfd.supporting_excerpts,
            bfd.metadata,
            bfd.created_at,
            bfd.updated_at,
            bfd.id
        FROM
            book_finder_chat_data bfd
            JOIN latest_question lq ON bfd.user_query = lq.user_query
        WHERE
            bfd.session_id = % s
            AND bfd.is_displayed = FALSE
        ORDER BY bfd.relevance_score DESC
        LIMIT % s
    ),
    displayed AS (
        SELECT bfd.*, TRUE AS is_displayed
        FROM
            book_finder_chat_data bfd
            JOIN latest_question lq ON bfd.user_query = lq.user_query
        WHERE
            bfd.session_id = % s
            AND bfd.is_displayed = TRUE
    ),
    total AS (
        SELECT COUNT(*) AS total_count
        FROM
            book_finder_chat_data bfd
            JOIN latest_question lq ON bfd.user_query = lq.user_query
        WHERE
            bfd.session_id = % s
    )

SELECT combined.*, total.total_count, latest_question.user_query
FROM (
        SELECT *
        FROM displayed
        UNION ALL
        SELECT u.*, FALSE AS is_displayed
        FROM undisplayed u
    ) combined
    CROSS JOIN total
    CROSS JOIN latest_question
ORDER BY combined.relevance_score DESC
LIMIT % s;