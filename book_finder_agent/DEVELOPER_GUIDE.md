# Book Finder Agent — Developer Guide

## Overview

This guide walks you through setting up, configuring, and running the Book Finder Agent locally for development and testing.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Local Development Setup](#local-development-setup)
3. [Environment Configuration](#environment-configuration)
4. [Database Setup](#database-setup)
5. [Running the Agent](#running-the-agent)
6. [Testing the Agent](#testing-the-agent)
7. [Troubleshooting](#troubleshooting)
8. [Development Workflow](#development-workflow)

---

## System Requirements

### Required
- **Python**: 3.10 or higher
- **PostgreSQL/AlloyDB**: 13.0 or higher (with pgvector extension)
- **pip**: Latest version (included with Python 3.10+)
- **Git**: For cloning the repository
- **Google Cloud SDK**: For Vertex AI embeddings (if using Google Cloud)

### Recommended
- **Virtual Environment**: `venv` or `conda`
- **Docker**: For containerized testing (optional)
- **Make**: For running common commands (optional)
- **curl** or **Postman**: For API testing

### System Resources
- **RAM**: 4 GB minimum, 8 GB recommended
- **Disk**: 2 GB for dependencies and data
- **Network**: Internet access for downloading Python packages and cloud APIs

---

## Local Development Setup

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd book_finder_agent
```

### Step 2: Create a Virtual Environment

#### Using venv (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### Using conda

```bash
conda create -n book-finder python=3.11
conda activate book-finder
```

### Step 3: Install Dependencies

Upgrade pip to the latest version:

```bash
pip install --upgrade pip setuptools wheel
```

Install project dependencies:

```bash
pip install -r requirements.txt
```

If you encounter issues with `psycopg2-binary`, install system-level PostgreSQL development libraries:

```bash
# macOS
brew install libpq

# Ubuntu/Debian
sudo apt-get install libpq-dev

# Fedora/RHEL
sudo dnf install postgresql-devel
```

Then reinstall:

```bash
pip install --force-reinstall psycopg2-binary
```

### Step 4: Verify Installation

Test that all key packages are installed:

```bash
python -c "import flask; import pydantic; import llm_studio_agents; print('All imports successful')"
```

---

## Environment Configuration

### Step 1: Create .env File

Copy the example environment file:

```bash
cp .env.example .env
```

### Step 2: Configure Critical Variables

Edit `.env` and fill in the following **mandatory** values:

#### Database Configuration

```bash
# PostgreSQL/AlloyDB Connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=book_finder_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
```

#### Google Cloud Configuration (if using Vertex AI)

```bash
# Google Cloud Project
GCLOUD_PROJECT_ID=your-gcp-project-id
GCLOUD_LOCATION=us-central1

# Service Account Authentication
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# PubSub Configuration (for streaming)
PUBSUB_PROJECT_ID=your-gcp-project-id
PUBSUB_TOPIC_NAME=book-finder-responses
```

#### LLM Configuration

```bash
# Vertex AI LLM Settings
LLM_MODEL_NAME=gemini-2.0-flash-001
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=1024
LLM_TOP_P=0.95
```

#### Application Configuration

```bash
# Server
PORT=5000
FLASK_ENV=development
SECRET_KEY=dev-secret-key-change-in-production

# Gunicorn (production)
WORKER_COUNT=4
WORKER_THREADS_COUNT=2
WORKER_TIMEOUT=120
MAX_REQUEST_TO_WORKER_RESTART=1000
WORKER_GRACEFUL_TIMEOUT=30
```

### Step 3: Validate Configuration

Test that configuration loads correctly:

```bash
python -c "import Config; Config.validate_configuration(); print('Configuration valid')"
```

If validation fails, the error message will indicate which variables are missing or invalid.

---

## Database Setup

### Step 1: Create Database and Extensions

Connect to PostgreSQL and create the database:

```bash
psql -U postgres -h localhost

-- Create database
CREATE DATABASE book_finder_db;

-- Connect to the new database
\c book_finder_db

-- Install pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
\dx
```

### Step 2: Initialize Session Context Table

The agent automatically creates the session context table on first run, but you can manually initialize it:

```bash
python -c "from book_finder_agent import BookFinderAgent; agent = BookFinderAgent(); agent.setup(config={}, data={}); print('Database initialized')"
```

Or execute the SQL directly:

```sql
CREATE TABLE IF NOT EXISTS book_retrieved_document_details (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    question TEXT NOT NULL,
    isbn VARCHAR(20) NOT NULL,
    context_score FLOAT DEFAULT 0.0,
    is_displayed BOOLEAN DEFAULT FALSE,
    is_expired BOOLEAN DEFAULT FALSE,
    display_count INTEGER DEFAULT 0,
    chunk_ids TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indices for performance
CREATE INDEX idx_session_question_expired ON book_retrieved_document_details(session_id, question, is_expired);
CREATE INDEX idx_session_displayed ON book_retrieved_document_details(session_id, is_displayed);
CREATE INDEX idx_context_score ON book_retrieved_document_details(context_score DESC);
```

### Step 3: Load Reference Data

If you have sample book data, load it into the appropriate tables:

```bash
# Example: Load CSV data into book_summary_backup_2
psql -U postgres -d book_finder_db -c "\COPY book_summary_backup_2 FROM 'data/books_summary.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',');"
```

---

## Running the Agent

### Option 1: Flask Development Server

#### Start the Agent

```bash
python run.py
```

Expected output:

```
 * Running on http://0.0.0.0:5000
 * Debug mode: ON
 * WARNING: This is a development server. Do not use it in production.
```

#### Verify the Agent is Running

In another terminal:

```bash
curl http://localhost:5000/utility/book-content-rag-agent/
```

Expected response:

```
Book Finder Agent is running!
```

### Option 2: Gunicorn (Production-like Local Testing)

```bash
gunicorn --workers 2 --worker-class gthread --threads 2 --bind 0.0.0.0:5000 run:app
```

### Option 3: Docker (Containerized)

```bash
# Build the image
docker build -t book-finder-agent .

# Run the container
docker run -p 5000:5000 \
  -e POSTGRES_HOST=host.docker.internal \
  -e POSTGRES_PASSWORD=your_password \
  -v /path/to/service-account-key.json:/app/credentials.json \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  book-finder-agent
```

---

## Testing the Agent

### Health Check Endpoint

```bash
curl http://localhost:5000/utility/book-content-rag-agent/health
```

Expected response:

```json
{"status": "healthy"}
```

### Configuration Endpoint

```bash
curl http://localhost:5000/utility/book-content-rag-agent/get_config
```

Returns the full configuration schema for the agent.

### Test Prediction Request

Create a file `test_request.json`:

```json
{
  "agent_id": "book-finder-v1",
  "concierge_id": "test-concierge",
  "session_id": "test-session-123",
  "question": "Find books about artificial intelligence",
  "agent_arguments": {
    "user_query": "Find books about artificial intelligence",
    "book_summary_details": null,
    "search_sentence": null,
    "genre_details": null,
    "quotes": null,
    "audience_details": null,
    "location_details": null,
    "contributor_details": null,
    "character_details": null,
    "contributor_biography_details": null,
    "prize_details": null,
    "section_details": null,
    "publisher_details": null,
    "imprint_details": null,
    "show_more_details": null
  },
  "agent_config": null
}
```

Send the request:

```bash
curl -X POST http://localhost:5000/utility/book-content-rag-agent/prediction \
  -H "Content-Type: application/json" \
  -d @test_request.json
```

Expected response:

```json
{
  "response": "Here are books about artificial intelligence...",
  "agent_guide": {
    "retrieved_documents": [...]
  },
  "sources": [...],
  "trace": {},
  "trace_root": null,
  "bypass_orchestrator_response": false
}
```

### Test Show More (Pagination)

Modify `test_request.json` to include `show_more_details`:

```json
{
  "show_more_details": {
    "length": 5,
    "question": "Find books about artificial intelligence"
  }
}
```

---

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'llm_studio_agents'`

**Solution**: Ensure you have installed the development dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

### Issue: `psycopg2.OperationalError: could not connect to server`

**Causes & Solutions**:

1. **PostgreSQL not running**:
   ```bash
   # macOS
   brew services start postgresql
   
   # Linux
   sudo systemctl start postgresql
   
   # Verify
   psql -U postgres -h localhost -d postgres -c "SELECT 1;"
   ```

2. **Incorrect credentials in .env**:
   - Verify `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
   - Test connection: `psql -U <user> -h <host> -p <port> -d <db>`

3. **Database does not exist**:
   ```bash
   psql -U postgres -h localhost -c "CREATE DATABASE book_finder_db;"
   ```

### Issue: `google.auth.exceptions.DefaultCredentialsError`

**Solution**: Set up Google Cloud credentials:

```bash
# Download service account key from Google Cloud Console
# Place in project directory or configure path
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# Verify
python -c "from google.oauth2 import service_account; print('Auth setup successful')"
```

### Issue: `AttributeError: 'NoneType' object has no attribute 'run'`

**Cause**: A tool was not properly initialized in agent `setup()`.

**Solution**:
1. Check that all tools are registered in `CONFIG_CLASS`
2. Verify tool configuration is present in the config dict
3. Add debug logging:
   ```python
   logging.debug(f"SQLExecutorTool: {self.sql_executor_tool}")
   logging.debug(f"LLMConfigTool: {self.llm_config_tool}")
   ```

### Issue: `Vector(1536) is not a valid type` in SQL queries

**Solution**: Ensure pgvector extension is installed:

```bash
psql -d book_finder_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -d book_finder_db -c "SELECT '1536'::vector;"
```

### Issue: Agent returns fallback response for all queries

**Debug Steps**:

1. Enable debug logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. Check that book data tables exist and contain data:
   ```sql
   SELECT COUNT(*) FROM book_summary_backup_2;
   SELECT COUNT(*) FROM book_content_chunked_backup_2;
   ```

3. Verify embeddings are being generated:
   ```bash
   curl -X POST http://localhost:5000/utility/book-content-rag-agent/prediction \
     -H "Content-Type: application/json" \
     -d '{"agent_id": "test", "session_id": "test", "question": "test"}' -v
   ```

4. Check logs for specific error messages

### Issue: Slow query performance

**Solutions**:

1. Verify indices exist:
   ```sql
   SELECT * FROM pg_indexes WHERE tablename = 'book_retrieved_document_details';
   ```

2. Rebuild indices if needed:
   ```sql
   REINDEX TABLE book_summary_backup_2;
   REINDEX TABLE book_content_chunked_backup_2;
   ```

3. Check pgvector index type:
   ```sql
   SELECT * FROM pg_indexes WHERE schemaname = 'public';
   ```

4. Increase `similarity_threshold` to reduce result set size

---

## Development Workflow

### Running Tests

```bash
python -m pytest tests/ -v
```

### Code Style and Linting

```bash
# Format code
black book_finder_agent/

# Lint
pylint book_finder_agent/

# Type checking
mypy book_finder_agent/
```

### Making Code Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and test locally**:
   ```bash
   python run.py  # in one terminal
   # test in another terminal
   ```

3. **Run full test suite before committing**:
   ```bash
   python -m pytest tests/
   black .
   pylint book_finder_agent/
   ```

4. **Commit with descriptive messages**:
   ```bash
   git add .
   git commit -m "feat: add support for filtering by publisher"
   ```

### Debugging

#### Enable Verbose Logging

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

#### Use a Debugger

```bash
python -m pdb run.py
```

Or in your IDE (VS Code, PyCharm), set breakpoints and use the integrated debugger.

---

## Next Steps

Once you have the agent running locally:

1. **Read CONFIG_REFERENCE.md** for detailed configuration options
2. **Check QUICKSTART.md** for common customizations
3. **Review INTEGRATION_CHECKLIST.md** before deploying to production
4. **See DEPLOYMENT_GUIDE.md** for production deployment steps

---

## Support and Contributing

For issues or questions:

1. Check this guide's Troubleshooting section
2. Review logs in `book_finder_agent.log` (if logging to file is enabled)
3. Open an issue on the project repository with:
   - Error message and full stack trace
   - Steps to reproduce
   - Your environment (Python version, OS, etc.)
   - Configuration (sanitized of credentials)

