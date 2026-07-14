-- Create session context table for persisting retrieved books across pagination
-- Idempotent operation: CREATE TABLE IF NOT EXISTS
-- Format placeholder: table_name

CREATE TABLE IF NOT EXISTS {table_name} (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    question TEXT NOT NULL,
    isbn VARCHAR(20) NOT NULL,
    context_score FLOAT DEFAULT 0.0,
    is_displayed BOOLEAN DEFAULT FALSE,
    is_expired BOOLEAN DEFAULT FALSE,
    display_count INTEGER DEFAULT 0,
    chunk_ids TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create composite index for efficient pagination queries
CREATE INDEX IF NOT EXISTS idx_session_question_expired
    ON {table_name} (session_id, question, is_expired)
    WHERE is_expired = FALSE;

CREATE INDEX IF NOT EXISTS idx_session_displayed
    ON {table_name} (session_id, question, is_displayed)
    WHERE is_displayed = FALSE;

CREATE INDEX IF NOT EXISTS idx_context_score
    ON {table_name} (context_score DESC)
    WHERE is_expired = FALSE;