-- Create session context table for storing and managing pagination state
-- This table persists intermediate retrieval results for "show more" and filtered query flows

CREATE TABLE IF NOT EXISTS book_finder_chat_data (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    question_id UUID NOT NULL,
    user_query TEXT NOT NULL,
    book_id UUID NOT NULL,
    relevance_score FLOAT8 DEFAULT 0.0,
    embedding_similarity FLOAT8 DEFAULT 0.0,
    filter_match_count INT DEFAULT 0,
    keyword_boost FLOAT8 DEFAULT 0.0,
    book_title VARCHAR(500),
    authors TEXT,
    genres TEXT,
    isbn VARCHAR(20),
    publication_date TIMESTAMP,
    summary TEXT,
    publisher VARCHAR(300),
    audience VARCHAR(100),
    supporting_excerpts JSONB DEFAULT '[]'::JSONB,
    metadata JSONB DEFAULT '{}'::JSONB,
    is_displayed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    CONSTRAINT unique_session_book UNIQUE(session_id, question_id, book_id),
    CONSTRAINT fk_session_id CHECK (session_id IS NOT NULL),
    CONSTRAINT fk_book_id CHECK (book_id IS NOT NULL)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_book_finder_session_question ON book_finder_chat_data (session_id, question_id);

CREATE INDEX IF NOT EXISTS idx_book_finder_book_id ON book_finder_chat_data (book_id);

CREATE INDEX IF NOT EXISTS idx_book_finder_relevance ON book_finder_chat_data (
    session_id,
    question_id,
    relevance_score DESC
);

CREATE INDEX IF NOT EXISTS idx_book_finder_displayed ON book_finder_chat_data (
    session_id,
    question_id,
    is_displayed
)
WHERE
    is_displayed = FALSE;

CREATE INDEX IF NOT EXISTS idx_book_finder_expires ON book_finder_chat_data (expires_at)
WHERE
    expires_at IS NOT NULL;