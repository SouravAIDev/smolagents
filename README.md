# Book Finder Agent

A production-ready retrieval augmented generation (RAG) agent for finding relevant book information through semantic search, supporting multi-filter queries, pagination, and evidence-backed responses with proper citations.

## Overview

The Book Finder Agent implements an advanced book discovery system that orchestrates multiple execution flows:

- **Flow A (Standard Processing)**: Semantic search across book metadata with multi-filter composition
- **Flow B (Show-More Pagination)**: Session-based pagination for browsing additional results
- **Flow C (Pre-Filtered Questions)**: JSONB-based filtering applied to cached session documents

## Architecture

The system is built on the LLM Studio framework and uses a modular architecture:

```
run.py (Flask Application Entry Point)
    ↓
book_finder_agent.py (Core Orchestration Agent)
    ↓
┌─────────────────────────────────────────────────┐
│ Utility Mixins                                  │
├─────────────────────────────────────────────────┤
│ • DatabaseRetrievalUtils                        │
│ • BookFinderUtilities                           │
│ • ShowMoreDetailsUtils                          │
│ • CitationUtils                                 │
│ • AIEmbeddingUtils                              │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│ External Tools                                  │
├─────────────────────────────────────────────────┤
│ • SQLExecutorTool (PostgreSQL + pgvector)       │
│ • LLMConfigurationTool (Prompt Engineering)     │
│ • SemanticSimilarityTool (Embeddings)           │
│ • CitationTool (Citation Generation)            │
└─────────────────────────────────────────────────┘
```

## Features

### Multi-Filter Book Search

Supports 17 distinct filter types for precise book discovery:

- Author Details & Biography
- Book Title, Summary, Publication Date
- Genre, Audience, ISBN, Publisher, Imprint
- Awards/Prizes, Location, Section, Character
- Supporting Excerpts & Quotes

### Semantic Search with Embeddings

- Uses pgvector for cosine similarity search
- Configurable similarity thresholds (default: 0.3)
- Supports both soft (semantic) and hard (exact) filtering
- Efficient vector-based retrieval across multiple tables

### Session Management

- Stateful pagination via session context table
- Automatic cleanup of old sessions (30-day default)
- JSONB-based metadata storage for flexible filtering
- Display state tracking to prevent duplicate results

### Citation & Evidence

- Markdown-based citation parsing from LLM responses
- Fuzzy matching for quote location detection
- Citation enrichment with book metadata (ISBN, publisher, dates)
- HTML formatting for UI consumption

### Scoring & Ranking

- Multi-weighted relevance scoring (context: 0.5, document: 0.2, keyword: 0.3)
- Configurable chunk retrieval boost for excerpt-backed results
- Threshold-based row reduction for quality control
- Normalization of final scores to [0, 1] range

## Installation

### Prerequisites

- Python 3.9+
- PostgreSQL 12+ with pgvector extension
- Redis 6.0+ (for caching and session state)
- Google Cloud SDK (for Vertex AI integrations)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd book-finder-agent
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your actual configuration values
   ```

5. **Initialize database**
   ```bash
   # Run SQL templates to create required tables
   # See queries/ directory for DDL scripts
   ```

## Configuration

All configuration is managed through environment variables (see `.env.example` for complete reference):

### Critical Settings

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=book_finder_db
DB_USER=postgres
DB_PASSWORD=your-password

# Embeddings
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# LLM
LLM_MODEL=gpt-4
OPENAI_API_KEY=sk-...

# Agent Behavior
MAX_BOOKS_PER_RESPONSE=3
SIMILARITY_THRESHOLD=0.3
FILTER_SIMILARITY_THRESHOLD=0.65
```

### Scoring Configuration

```env
CONTEXT_WEIGHT_SCORE=0.5      # Weight for context relevance
DOCUMENT_WEIGHT_SCORE=0.2     # Weight for document relevance
KEYWORD_WEIGHT_SCORE=0.3      # Weight for keyword matching
CHUNK_RETRIEVAL_DOCUMENT_BOOST=0.2  # Bonus for excerpt-backed results
```

## Usage

### Starting the Service

```bash
# Development
python run.py

# Production with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

### API Endpoints

#### Health Check

```bash
GET /utility/book-finder-agent/
GET /utility/book-finder-agent/health
```

Response: Agent status indicator

#### Prediction (Book Search)

```bash
POST /utility/book-finder-agent/prediction
Content-Type: application/json

{
  "agent_id": "agent-123",
  "concierge_id": "concierge-456",
  "agent_arguments": {
    "user_query": "Find books about climate change by scientists",
    "genre_details": "Science & Nature",
    "author_details": "climate scientist",
    "supporting_excerpts": "global warming evidence"
  }
}
```

Response:
```json
{
  "response": "Here are relevant books matching your query...",
  "agent_guide": {
    "retrieved_documents": [
      {
        "book_id": "uuid-123",
        "title": "The Climate Book",
        "author_name": "Dr. Jane Smith",
        "isbn": "978-0-12345-678-9",
        "similarity_score": 0.87,
        "final_score": 0.85
      }
    ]
  },
  "sources": [
    {
      "book_id": "uuid-123",
      "title": "The Climate Book",
      "author": "Dr. Jane Smith",
      "isbn": "978-0-12345-678-9",
      "excerpt": "Excerpt from the book..."
    }
  ]
}
```

#### Get Configuration Schema

```bash
GET /utility/book-finder-agent/get_config
```

Returns: Agent configuration schema for UI builder integration

#### Get LLM Configuration

```bash
GET /utility/book-finder-agent/get_llm_config
```

Returns: LLM-specific configuration and prompts

## Filter Types Reference

Each filter type maps to specific database tables and embedding columns:

| Filter Type | Table | Search Column | Mode | 
|---|---|---|---|
| `book_summary` | book_metadata_v2 | book_summary_embeddings | soft |
| `book_title` | book_metadata_v2 | title_embeddings | soft |
| `author_details` | book_author_v2 | author_name_embeddings | soft |
| `genre_details` | book_metadata_v2 | genre_embeddings | hard |
| `publisher_details` | book_metadata_v2 | publisher_name_embeddings | soft |
| `supporting_excerpts` | book_excerpts_v2 | excerpt_embeddings | soft |

(See `book_helper.py` for complete mapping)

## Database Schema

### Primary Tables

- `book_metadata_v2` - Book information (title, ISBN, genre, summary)
- `book_author_v2` - Author associations
- `book_author_normalized` - Normalized author data
- `book_genre_v2` - Genre classifications
- `book_award_v2` - Award information
- `book_excerpts_v2` - Supporting manuscript excerpts
- `book_publisher` - Publisher metadata

### Session Management Tables

- `book_retrieved_document_details` - Session context and pagination state
  - Columns: `session_id`, `book_id`, `question`, `book_data` (JSONB), `is_displayed`, `similarity_score`, `created_at`, `updated_at`
  - Indexes: session_id, is_displayed, similarity_score, created_at

### SQL Templates

Query templates in `queries/` directory:

- `vector_query.sql` - Core pgvector similarity search
- `create_chat_data_table.sql` - Session context schema
- `insert_retrieved_documents.sql` - Pagination data persistence
- `fetch_show_more_docs.sql` - Pagination retrieval
- `mark_books_as_displayed.sql` - Display state updates
- `fetch_latest_question_for_session.sql` - Context recovery
- `filter_query_exact_match.sql` - Hard filter matching
- `fetch_filtered_documents.sql` - JSONB filtering
- `upsert_retrieved_documents.sql` - Lifecycle management
- `vector_filter_query_with_join.sql` - Complex multi-table joins
- `fallback_fetch_show_more_docs.sql` - Fallback retrieval
- `retrieve_final_chunks.sql` - Excerpt enrichment

## Execution Flows

### Flow A: Standard Request Processing

1. **A1-A3**: Input validation and normalization
2. **A4**: Semantic search across filter types
   - Generate query embedding
   - Execute pgvector searches for each active filter
   - Aggregate results with similarity scores
3. **A5**: Content enrichment and scoring
   - Calculate final relevance scores
   - Reduce to top-scoring books
   - Retrieve supporting excerpts
   - Store in session context
   - Generate LLM response with citations

### Flow B: Pagination (Show-More)

1. **B1**: Fetch undisplayed documents from session
   - Query cached results where `is_displayed = FALSE`
   - Mark selected books as displayed
   - Return ranked pagination results

### Flow C: Pre-Filtered Questions

1. **C1**: Apply filters to session context
   - Fetch latest question for session
   - Apply JSONB filters to `book_data`
   - Return filtered results

## Performance Tuning

### Database Optimization

1. **Create pgvector indexes**:
   ```sql
   CREATE INDEX idx_book_summary_embeddings ON book_metadata_v2 USING ivfflat (book_summary_embeddings vector_cosine_ops);
   ```

2. **Connection pooling**:
   - `DB_POOL_SIZE=20` (default)
   - `DB_MAX_OVERFLOW=10` (burst capacity)
   - `DB_POOL_RECYCLE=3600` (idle connection timeout)

3. **Redis caching**:
   - Session state in Redis
   - Configurable TTL based on `SESSION_EXPIRATION_DAYS`

### Scoring Optimization

Adjust weights to improve result relevance:

```env
CONTEXT_WEIGHT_SCORE=0.5      # Increase for more context-aware ranking
DOCUMENT_WEIGHT_SCORE=0.2     # Increase for stricter document matching
KEYWORD_WEIGHT_SCORE=0.3      # Increase for keyword importance
```

## Troubleshooting

### No Results Returned

1. Check similarity thresholds:
   ```python
   # Current: SIMILARITY_THRESHOLD=0.3 (30% similarity)
   # Try lowering to 0.2 for broader matches
   ```

2. Verify embeddings generated:
   ```bash
   # Check if embedding_dimensions match (usually 1536)
   curl http://localhost:5000/utility/book-finder-agent/get_llm_config
   ```

3. Check database indexes:
   ```sql
   SELECT * FROM pg_stat_user_indexes WHERE idx_definition LIKE '%embedding%';
   ```

### Slow Response Times

1. Increase `DB_POOL_SIZE` for more concurrent connections
2. Enable Redis caching for frequently accessed data
3. Add database indexes on commonly filtered columns
4. Reduce `MAX_BOOKS_PER_RESPONSE` to limit processing

### Citation Failures

1. Verify LLM response format (must include `[source_N]` markers)
2. Check `retrieved_documents` structure matches citation extraction logic
3. Enable `SHOW_HEADERS=True` for debugging output

## Monitoring & Logging

### Log Levels

```env
LOG_LEVEL=INFO           # Development: DEBUG, Production: INFO
LOG_FORMAT=json          # JSON formatting for parsing
GOOGLE_CLOUD_LOGGING=True  # Stream to Google Cloud Logging
```

### Key Metrics

- Query latency (embedding generation + search)
- Results per query (books retrieved)
- Citation success rate
- Session state size
- Database connection pool utilization

### Health Check

```bash
curl http://localhost:5000/utility/book-finder-agent/health
```

## Contributing

To extend the agent:

1. **Add new filter type**:
   - Update `BookFilterType` enum in `book_helper.py`
   - Add `FilterDetails` mapping in `BOOK_FILTER_MAPPING`
   - Create corresponding SQL templates in `queries/`

2. **Modify scoring logic**:
   - Adjust weights in `Config.py` or `book_finder_agent_setup.py`
   - Update `calculate_final_scores()` in `book_finder_utilities.py`

3. **Improve citations**:
   - Enhance `CitationUtils` methods for better quote matching
   - Add metadata enrichment for additional book details

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "run:app"]
```

### Kubernetes

See `k8s-deployment.yaml` for production deployment configuration with:
- Resource limits and requests
- Liveness and readiness probes
- Environment secret management
- Horizontal pod autoscaling

### Environment Variables (Production)

Always set critical values:

```bash
export FLASK_ENV=production
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
export DB_PASSWORD=secure-password-here
export OPENAI_API_KEY=sk-...
```

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions, please open an issue on GitHub or contact the development team.

