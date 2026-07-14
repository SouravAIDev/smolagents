-- Session context table for storing retrieved books and pagination state.
-- Parameters: {context_table}, {embedding_dim}
-- doc_id stores ISBN for BookFinderAgent (or contract_id for contracts).
-- query_embeddings stores the user query vector for similarity calculations.

CREATE TABLE IF NOT EXISTS {context_table} (
    id SERIAL PRIMARY KEY,
    session_id TEXT,
    doc_id TEXT,
    question TEXT,
    query_embeddings VECTOR({embedding_dim}),
    doc_context JSONB,
    is_displayed BOOLEAN DEFAULT FALSE,
    is_expired BOOLEAN DEFAULT FALSE,
    created_date TIMESTAMP DEFAULT NOW(),
    context_score FLOAT DEFAULT 0.0,
    display_count INT DEFAULT 0
);