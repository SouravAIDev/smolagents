-- Fetch documents from session context filtered by JSONB metadata criteria
-- Used to enable filtered context retrieval (Flow C) when user applies structured
-- filters to refine results from a previous query.
--
-- Query: Retrieves cached book records from book_finder_chat_data where the metadata
-- JSONB column contains specified filter keys and values. Supports multiple filter types
-- (genre, author, publisher, audience, etc.) via dynamic WHERE clauses.
--
-- Parameters:
--   session_id (UUID): The session identifier
--   question_id (UUID): The question identifier for context scoping
--   filter_type (text): The metadata key to filter on (e.g., 'genres', 'authors')
--   filter_values (text[]): Array of allowed values for the filter (e.g., ['Fiction', 'Mystery'])
--
-- Returns:
--   All book and metadata fields from book_finder_chat_data matching filters,
--   ordered by relevance_score DESC.

SELECT
    session_id,
    question_id,
    user_query,
    book_id,
    title,
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
FROM
    book_finder_chat_data
WHERE
    session_id = %s
    AND question_id = %s
    AND (
        -- JSONB filtering: check if metadata contains the filter key with matching values
        -- Example: metadata @> '{"genres": ["Fiction"]}' for genre filtering
        CASE
            WHEN %s = 'genres' THEN (metadata -> 'genres') ? ANY(%s::text[])
            WHEN %s = 'authors' THEN (metadata -> 'authors') ? ANY(%s::text[])
            WHEN %s = 'publisher' THEN (metadata -> 'publisher') ? ANY(%s::text[])
            WHEN %s = 'audience' THEN (metadata -> 'audience') ? ANY(%s::text[])
            WHEN %s = 'isbn' THEN (metadata -> 'isbn') ? ANY(%s::text[])
            ELSE TRUE  -- If filter type not recognized, return all records
        END
    )
ORDER BY
    relevance_score DESC,
    created_at ASC
LIMIT %s;