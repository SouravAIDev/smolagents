# Book Finder Agent — Complete System Deployment Guide

## System Architecture Overview

### What is the Book Finder Agent?

The Book Finder Agent is a production-ready microservice that accepts natural language queries about books and returns:
1. **Ranked results** — books matched using semantic and exact-match hybrid search
2. **Supporting metadata** — genres, authors, publishers, publication dates, summaries
3. **Evidence-backed citations** — direct excerpts linked to LLM-generated responses
4. **Three execution modes:**
   - **Standard Retrieval** — semantic search + exact matching + relevance scoring
   - **Pagination** — show more results from cached session context
   - **Filtered Refinement** — apply new filters to previous session results

### Technology Stack

- **Language:** Python 3.9+
- **Web Framework:** Flask + Gunicorn
- **Database:** PostgreSQL with pgvector extension
- **LLM Integration:** Gemini 2.0 Flash (configurable)
- **Embedding:** SemanticSimilarityTool (LLM Studio)
- **Deployment:** Docker or direct Python WSGI

---

## Complete File Structure

```
project-root/
├── run.py                              # Flask entry point, HTTP routing
├── config.py                           # Configuration schema, defaults
├── requirements.txt                    # Python dependencies
├── book_finder_helpers.py              # Request validation, citations
├── .env                                # Environment variables (not in repo)
├── .env.example                        # Example environment variables
│
├── agents/
│   └── book_finder_agent/
│       ├── __init__.py                 # Package initialization
│       ├── book_finder_agent.py        # Main agent class (1160 lines)
│       ├── book_finder_setup.py        # Configuration schema (Pydantic)
│       ├── book_finder_trace.py        # Trace schema for observability
│       ├── book_finder_filters.py      # Filter configuration & mapping
│       ├── book_finder_utilities.py    # Data normalization utilities
│       ├── book_finder_retrieval_utils.py  # Database query helpers
│       ├── book_finder_pagination_helpers.py  # Flow B pagination logic
│       ├── book_finder_filtering_helpers.py   # Flow C filtering logic
│       └── queries/                    # SQL templates (12 files)
│           ├── create_chat_data_table.sql
│           ├── retrieve_books_semantic.sql
│           ├── retrieve_books_exact_match.sql
│           ├── fetch_show_more_docs.sql
│           ├── fallback_fetch_show_more_docs.sql
│           ├── fetch_latest_question_for_session.sql
│           ├── fetch_filtered_question_documents.sql
│           ├── insert_retrieved_documents.sql
│           ├── upsert_retrieved_documents.sql
│           ├── mark_books_as_displayed.sql
│           ├── retrieve_session_context.sql
│           └── expire_old_sessions.sql
│
├── INTEGRATION_VERIFICATION.md         # Detailed integration checklist
├── SYSTEM_DEPLOYMENT_GUIDE.md          # This file
└── README.md                            # Quick start guide
```

---

## Prerequisites & Installation

### System Requirements

- **OS:** Linux, macOS, or Windows (WSL2)
- **Python:** 3.9 or later
- **PostgreSQL:** 12.0 or later with pgvector extension
- **Memory:** 2GB minimum (4GB recommended)
- **Disk:** 500MB for application + database size depends on book collection

### Step 1: Clone Repository & Install Dependencies

```bash
# Clone or download the project
cd book-finder-agent

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
nano .env  # or your preferred editor
```

**Required Environment Variables:**

```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key-here-min-32-chars

# Database Configuration
DATABASE_URI=postgresql://user:password@localhost:5432/book_finder_db

# LLM Configuration (Gemini)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash

# Embeddings Configuration
EMBEDDING_PROVIDER=google  # or openai
EMBEDDING_API_KEY=your-embedding-api-key
EMBEDDING_MODEL=text-embedding-3-large

# Optional: Google Cloud Logging
GCP_PROJECT_ID=your-gcp-project
GCP_LOG_NAME=book-finder-agent

# Server Configuration
GUNICORN_WORKERS=4
GUNICORN_TIMEOUT=30
```

### Step 3: Set Up PostgreSQL Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE book_finder_db;

# Connect to new database
\c book_finder_db

# Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

# Create schema (the agent will create tables automatically on first run)
# OR manually run the SQL files from agents/book_finder_agent/queries/create_chat_data_table.sql
```

**Install pgvector (if not already installed):**

```bash
# Ubuntu/Debian
sudo apt-get install postgresql-contrib
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Or with Homebrew (macOS)
brew install pgvector
```

### Step 4: Verify Installation

```bash
# Check Python dependencies
python -c "from flask import Flask; print('✅ Flask installed')"

# Check database connection
python -c "import psycopg2; psycopg2.connect('postgresql://user:password@localhost/book_finder_db'); print('✅ Database connected')"

# Check LLM Studio integration
python -c "from llm_studio_agents.AgentBase import AgentBase; print('✅ LLM Studio available')"
```

---

## Running the Application

### Development Mode (Flask Development Server)

```bash
# Start Flask development server (single-threaded, auto-reload)
flask run --reload

# Server will be available at http://localhost:5000
```

**⚠️ Note:** Development server is NOT suitable for production. Use Gunicorn for production.

### Production Mode (Gunicorn WSGI Server)

```bash
# Start Gunicorn with 4 worker processes
gunicorn -w 4 \
  -b 0.0.0.0:8000 \
  -t 30 \
  --max-requests 1000 \
  --max-requests-jitter 100 \
  --timeout 30 \
  run:app

# Server will be available at http://0.0.0.0:8000
```

**Gunicorn Parameters:**
- `-w 4`: 4 worker processes (adjust based on CPU cores)
- `-b 0.0.0.0:8000`: Bind to all interfaces on port 8000
- `-t 30`: Worker timeout of 30 seconds
- `--max-requests 1000`: Restart worker after 1000 requests
- `--timeout 30`: Hard timeout for requests

### Docker Deployment

```bash
# Build Docker image
docker build -t book-finder-agent .

# Run container
docker run -p 8000:8000 \
  -e DATABASE_URI="postgresql://user:password@host:5432/db" \
  -e GEMINI_API_KEY="your-api-key" \
  -e FLASK_ENV=production \
  book-finder-agent

# Or with docker-compose
docker-compose up -d
```

---

## Testing the Agent

### Health Check

```bash
# Verify the server is running
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Standard Retrieval Request

```bash
curl -X POST http://localhost:8000/utility/book-finder-agent/prediction \
  -H "Content-Type: application/json" \
  -d '{
    "search_query": "fiction books about adventure and mystery",
    "session_id": "user-123-session-001",
    "agent_arguments": {
      "search_query": "fiction books about adventure and mystery",
      "session_id": "user-123-session-001",
      "is_show_more": false
    },
    "agent_config": {
      "tools": {
        "SQLExecutorTool": {...},
        "SemanticSimilarityTool": {...}
      },
      "BookFinderAgentSetup": {
        "max_results_per_query": 10,
        "semantic_similarity_threshold": 0.65
      }
    }
  }'
```

**Expected Response (HTTP 200):**

```json
{
  "response": "I found 5 fiction books about adventure and mystery...",
  "retrieved_documents": {
    "books": [
      {
        "book_id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "The Adventure Mystery",
        "authors": "John Smith, Jane Doe",
        "genres": "Fiction, Mystery, Adventure",
        "isbn": "978-0-123456-789",
        "publication_date": "2020-01-15",
        "summary": "A thrilling adventure...",
        "publisher": "Adventure Press",
        "audience": "Adult"
      }
    ],
    "chunks": [
      {
        "chunk_id": "chunk-001",
        "book_id": "550e8400-e29b-41d4-a716-446655440000",
        "text": "In the dark forest, the protagonist discovers...",
        "similarity_score": 0.92
      }
    ],
    "book_count": 5,
    "chunk_count": 12,
    "uuid_mapping": {"550e8400-e29b-41d4-a716-446655440000": "1"}
  },
  "sources": [
    {
      "citation_number": 1,
      "source_book_id": "550e8400-e29b-41d4-a716-446655440000",
      "source_type": "book_summary",
      "highlighted_text": "A thrilling adventure into the unknown",
      "citation_score": 0.92,
      "metadata": {
        "book_title": "The Adventure Mystery",
        "author": "John Smith",
        "isbn": "978-0-123456-789",
        "publication_date": "2020-01-15"
      }
    }
  ],
  "trace": {
    "root": {
      "correlation_id": "req-123-abc",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    "retrieval_time_ms": 450,
    "scoring_time_ms": 120,
    "llm_generation_time_ms": 800
  },
  "bypass_orchestrator_response": false
}
```

### Pagination Request (Show More)

```bash
curl -X POST http://localhost:8000/utility/book-finder-agent/prediction \
  -H "Content-Type: application/json" \
  -d '{
    "search_query": "fiction books about adventure",
    "session_id": "user-123-session-001",
    "is_show_more": true,
    "agent_arguments": {
      "search_query": "fiction books about adventure",
      "session_id": "user-123-session-001",
      "is_show_more": true
    }
  }'
```

This will retrieve undisplayed books from the previous query's session context.

### Filtering Request (Refine Results)

```bash
curl -X POST http://localhost:8000/utility/book-finder-agent/prediction \
  -H "Content-Type: application/json" \
  -d '{
    "search_query": "fiction books about adventure",
    "session_id": "user-123-session-001",
    "metadata": {
      "filtered_question": true,
      "selected_filters": {
        "genre": ["Mystery"],
        "publisher": ["Adventure Press"],
        "audience": ["Adult"]
      }
    },
    "agent_arguments": {
      "search_query": "fiction books about adventure",
      "session_id": "user-123-session-001"
    }
  }'
```

This will apply JSONB-based filtering to previous results.

---

## Error Handling & Debugging

### Common Errors & Solutions

#### 1. Database Connection Error

**Error:**
```
DatabaseConnectionError: Failed to connect: could not connect to server
```

**Solution:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U user -d book_finder_db -h localhost

# Verify DATABASE_URI format in .env
# Should be: postgresql://user:password@host:port/database
```

#### 2. Missing SQL Templates

**Error:**
```
ConfigurationError: Missing mandatory SQL templates: ['retrieve_books_semantic']
```

**Solution:**
```bash
# Ensure SQL files exist in agents/book_finder_agent/queries/
ls -la agents/book_finder_agent/queries/

# Verify file has correct name (must match template name in REQUIRED_TEMPLATES)
# Example: retrieve_books_semantic.sql → template name is "retrieve_books_semantic"
```

#### 3. JSON Parse Error

**Error:**
```
HTTP 400: Invalid JSON in request body
```

**Solution:**
```bash
# Validate JSON before sending
jq . <<< '{"search_query": "books"}'

# Common issues:
# - Missing commas between fields
# - Unescaped quotes in strings
# - Trailing commas in objects/arrays
```

#### 4. Timeout Error

**Error:**
```
DatabaseError: QueryCanceled: canceling statement due to user request
```

**Solution:**
```bash
# Increase query timeout in config.py
# Or for specific users, use user_role='admin' to get 300s timeout

# Check for slow queries in PostgreSQL logs
less /var/log/postgresql/postgresql.log
```

#### 5. No Results Found

**Symptom:** Agent returns fallback response despite having matching books

**Debugging:**
```bash
# Check similarity threshold is not too high
# In config.py: semantic_similarity_threshold should be 0.5-0.75

# Check book data is properly indexed
SELECT COUNT(*) FROM books;
SELECT COUNT(*) FROM book_summaries WHERE summary_embedding IS NOT NULL;

# Check filter mappings exist for your filter types
ls -la agents/book_finder_agent/book_finder_filters.py
```

### Enabling Debug Logging

```python
# In run.py or config.py, add:
import logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

OR via environment variable:
```bash
export LOG_LEVEL=DEBUG
```

### Monitoring & Metrics

**Key metrics to track:**
- Request count per endpoint
- Response time (ms) per request
- Error rate (HTTP 400, 500)
- Database query execution time
- Cache hit rate (for pagination/filtering)

**Access logs:**
```bash
# Flask development server
# Logs printed to console

# Gunicorn
# Access logs: /var/log/gunicorn/access.log
# Error logs: /var/log/gunicorn/error.log

# Google Cloud Logging (if configured)
# Logs available in GCP Console
```

---

## Production Deployment Checklist

### Pre-Deployment ✅

- [ ] All environment variables set in production environment
- [ ] Database backup created
- [ ] SSL/TLS certificates configured (if using HTTPS)
- [ ] Firewall rules configured (PostgreSQL access restricted)
- [ ] API authentication configured (if required)
- [ ] Rate limiting configured (if required)
- [ ] Log aggregation configured (Stackdriver, DataDog, etc.)
- [ ] Monitoring alerts set up
- [ ] Disaster recovery plan documented

### Deployment ✅

- [ ] Pull latest code from repository
- [ ] Run database migrations (if any)
- [ ] Update Python dependencies: `pip install -r requirements.txt`
- [ ] Run health checks
- [ ] Start Gunicorn workers with correct configuration
- [ ] Verify application logs for startup errors
- [ ] Test all three execution flows (retrieval, pagination, filtering)
- [ ] Load test with expected traffic volume

### Post-Deployment ✅

- [ ] Monitor error rates and response times
- [ ] Verify database backups are running
- [ ] Check log files for warnings or errors
- [ ] Verify citation quality
- [ ] Test pagination with multiple sessions
- [ ] Verify timeouts for different user roles
- [ ] Document any configuration changes
- [ ] Schedule regular database maintenance (VACUUM, ANALYZE)

### Maintenance & Operations ✅

**Daily:**
- Monitor error rates
- Check disk space
- Review slow query logs

**Weekly:**
- Run VACUUM on PostgreSQL
- Review application logs for patterns
- Check backup integrity

**Monthly:**
- Update dependencies (security patches)
- Review and optimize slow queries
- Analyze user feedback and improve prompts
- Test disaster recovery procedures

---

## Configuration Reference

### Key Configuration Parameters

```python
# In agents/book_finder_agent/book_finder_setup.py or config.py

# Retrieval Parameters
max_results_per_query = 10  # Maximum books to retrieve per query
page_size = 5  # Results per pagination request
show_more_batch_size = 5  # Results to return on show-more

# Scoring Parameters
embedding_similarity_weight = 0.5  # Weight for semantic similarity
filter_match_weight = 0.3  # Weight for filter matches
keyword_boost_weight = 0.2  # Weight for keyword matching
reduce_contracts_rows_threshold = 0.3  # Quality threshold (0-1)
min_documents_to_shortlist = 8  # Minimum books to return

# Similarity Thresholds
semantic_similarity_threshold = 0.65  # Minimum pgvector similarity
citation_confidence_threshold = 0.5  # Minimum citation score

# Session Management
session_expiry_hours = 24  # How long to keep session context

# LLM Parameters
llm_temperature = 0.7  # Creativity (0=deterministic, 1=random)
llm_max_tokens = 1000  # Maximum response length
enable_llm_generation = True  # Whether to use LLM for response text
enable_citation_generation = True  # Whether to extract citations

# Timeout Policies
default_query_timeout = 30  # Seconds for standard users
admin_query_timeout = 300  # Seconds for admin/report users

# Feature Toggles
enable_semantic_search = True  # Use pgvector similarity
enable_exact_match_filter = True  # Use exact-match filtering
enable_pagination = True  # Allow show-more requests
enable_filtering = True  # Allow filtered refinement
```

---

## Performance Optimization

### Database Optimization

```sql
-- Regular maintenance
VACUUM ANALYZE;  -- Reclaim space and update statistics

-- Check index usage
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'public';

-- Find slow queries
SELECT query, calls, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;
```

### Caching Strategies

1. **Session Context Caching** — Results cached in book_finder_chat_data table for pagination
2. **Query Result Caching** — Consider Redis for frequently asked questions
3. **Embedding Caching** — Embed book summaries once, reuse indefinitely

### Query Optimization

1. **Use indexes** — Verify indexes exist on search columns
2. **Limit result sets** — Use LIMIT clauses appropriately
3. **Batch operations** — Use bulk INSERT/UPDATE for multiple documents
4. **Connection pooling** — Reuse database connections

---

## Summary

The Book Finder Agent is now deployed and ready for production use. Key capabilities:

✅ **Standard Retrieval** — Semantic + exact-match hybrid search with ranking
✅ **Pagination** — Retrieve more results from cached session context
✅ **Filtering** — Apply JSONB-based filters to refine previous results
✅ **Citations** — Extract evidence-backed citations from LLM responses
✅ **Error Handling** — Graceful degradation with appropriate HTTP status codes
✅ **Observability** — Comprehensive logging and request tracing
✅ **Scalability** — Multi-worker Gunicorn deployment ready

For support and documentation:
- See INTEGRATION_VERIFICATION.md for detailed architecture
- See README.md for quick start
- Check application logs for detailed error messages


