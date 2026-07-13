-- Insert newly retrieved books into the session context table
-- Used by Step A5 to persist retrieval results for pagination and filtering
-- Bulk insert multiple books in a single transaction

INSERT INTO
    book_finder_chat_data (
        session_id,
        question_id,
        user_query,
        book_id,
        relevance_score,
        embedding_similarity,
        filter_match_count,
        keyword_boost,
        book_title,
        authors,
        genres,
        isbn,
        publication_date,
        summary,
        publisher,
        audience,
        supporting_excerpts,
        metadata,
        is_displayed,
        expires_at
    )
VALUES
    % s ON CONFLICT (
        session_id,
        question_id,
        book_id
    ) DO
UPDATE
SET
    relevance_score = EXCLUDED.relevance_score,
    embedding_similarity = EXCLUDED.embedding_similarity,
    filter_match_count = EXCLUDED.filter_match_count,
    keyword_boost = EXCLUDED.keyword_boost,
    updated_at = CURRENT_TIMESTAMP,
    expires_at = EXCLUDED.expires_at RETURNING book_id,
    relevance_score,
    is_displayed;