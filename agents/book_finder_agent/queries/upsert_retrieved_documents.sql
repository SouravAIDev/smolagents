-- Update relevance scores and metadata for previously retrieved documents
-- Used during re-ranking or re-scoring passes within the same session
-- Preserves creation timestamp while updating scores and metadata

UPDATE book_finder_chat_data
SET
    relevance_score = % s,
    embedding_similarity = % s,
    filter_match_count = % s,
    keyword_boost = % s,
    supporting_excerpts = % s,
    metadata = % s,
    updated_at = CURRENT_TIMESTAMP
WHERE
    session_id = % s
    AND question_id = % s
    AND book_id = % s RETURNING book_id,
    relevance_score,
    is_displayed,
    updated_at;