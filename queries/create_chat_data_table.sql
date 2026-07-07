-- Create session context table for storing retrieved documents and pagination state
-- This table maintains the history of retrieved books for a user session
CREATE TABLE IF NOT EXISTS {context_table} (
    session_id UUID NOT NULL,
    book_id UUID NOT NULL,
    question TEXT NOT NULL,
    book_data JSONB NOT NULL DEFAULT '{}',
    is_displayed BOOLEAN DEFAULT FALSE,
    similarity_score FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, book_id)
);

-- Index for efficient session lookups
CREATE INDEX IF NOT EXISTS idx_{context_table}_session_id
    ON {context_table}(session_id);

-- Index for efficient filtering by display status
CREATE INDEX IF NOT EXISTS idx_{context_table}_displayed
    ON {context_table}(session_id, is_displayed);

-- Index for efficient sorting by similarity score
CREATE INDEX IF NOT EXISTS idx_{context_table}_similarity
    ON {context_table}(session_id, similarity_score DESC);

-- Index for cleanup queries filtering by created_at
CREATE INDEX IF NOT EXISTS idx_{context_table}_created_at
    ON {context_table}(created_at);