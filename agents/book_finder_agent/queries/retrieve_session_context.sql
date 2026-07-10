-- Retrieve all documents for a specific session and question
-- Used by Flow C (pre-filtered query) and pagination fallback scenarios
-- Returns all available books (displayed and undisplayed) for the session

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
    is_displayed,
    created_at,
    updated_at
FROM book_finder_chat_data
WHERE
    session_id = % s
    AND question_id = % s
ORDER BY relevance_score DESC, created_at ASC;