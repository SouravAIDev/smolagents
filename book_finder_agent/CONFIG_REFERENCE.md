# Book Finder Agent — Configuration Reference

Complete documentation of all environment variables and configuration parameters for the Book Finder Agent.

## Table of Contents

1. [Database Configuration](#database-configuration)
2. [Google Cloud Configuration](#google-cloud-configuration)
3. [Application Configuration](#application-configuration)
4. [Gunicorn (Production Server) Configuration](#gunicorn-production-server-configuration)
5. [LLM Configuration](#llm-configuration)
6. [Retrieval Configuration](#retrieval-configuration)
7. [Scoring Configuration](#scoring-configuration)
8. [Table Names Configuration](#table-names-configuration)
9. [Citation and Verification Configuration](#citation-and-verification-configuration)
10. [Configuration Validation](#configuration-validation)

---

## Database Configuration

### POSTGRES_HOST

**Type**: `string`  
**Default**: `localhost`  
**Valid Values**: Hostname or IP address  
**Required**: Yes (for production)

**Description**: PostgreSQL/AlloyDB server hostname or IP address.

**Impact**: Determines which database server the agent connects to.

**Examples**:
```bash
POSTGRES_HOST=localhost                    # Local development
POSTGRES_HOST=alloydb.example.com         # AlloyDB instance
POSTGRES_HOST=10.0.1.50                   # Private IP in VPC
```

### POSTGRES_PORT

**Type**: `integer`  
**Default**: `5432`  
**Valid Range**: 1024-65535  
**Required**: No

**Description**: PostgreSQL server port.

**Impact**: Must match the port your database listens on.

**Examples**:
```bash
POSTGRES_PORT=5432  # Standard PostgreSQL
POSTGRES_PORT=5433  # Non-standard port
```

### POSTGRES_DB

**Type**: `string`  
**Default**: `book_finder_db`  
**Valid Values**: Alphanumeric, underscores, hyphens  
**Required**: Yes

**Description**: PostgreSQL database name.

**Impact**: Specifies which database to connect to within the PostgreSQL server.

### POSTGRES_USER

**Type**: `string`  
**Default**: `postgres`  
**Required**: Yes

**Description**: PostgreSQL username for authentication.

**Security Note**: Use a dedicated read-write user, not the superuser `postgres`.

### POSTGRES_PASSWORD

**Type**: `string`  
**Default**: None (no default, must be set)  
**Required**: Yes (in production)

**Description**: PostgreSQL password for authentication.

**Security Recommendations**:
- Store in environment variables or secrets manager, never in code
- Use strong passwords (20+ characters, mixed case, symbols)
- Rotate quarterly

---

## Google Cloud Configuration

### GCLOUD_PROJECT_ID

**Type**: `string`  
**Default**: None  
**Required**: Yes (for Vertex AI features)

**Description**: Google Cloud Project ID where Vertex AI and other GCP services run.

**Impact**: Required for:
- Embedding generation via Vertex AI
- LLM calls via Gemini models
- PubSub streaming (if enabled)

**Example**:
```bash
GCLOUD_PROJECT_ID=my-company-prod-123
```

### GCLOUD_LOCATION

**Type**: `string`  
**Default**: `us-central1`  
**Valid Values**: GCP regions (us-central1, us-west1, europe-west1, etc.)  
**Required**: No

**Description**: Default Google Cloud region for API calls.

**Impact**: Affects latency and data residency for Vertex AI API calls.

**Supported Regions**:
- us-central1 (lowest latency for US)
- europe-west1 (for EU data residency)
- asia-southeast1 (for Asia)

### GOOGLE_APPLICATION_CREDENTIALS

**Type**: `string` (file path)  
**Default**: None  
**Required**: Yes (for GCP authentication)

**Description**: Path to Google Cloud service account JSON key file.

**Impact**: Enables authentication to all GCP services (Vertex AI, Logging, PubSub).

**Setup**:
```bash
# Download from GCP Console
# Place in project directory or secure location
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### PUBSUB_PROJECT_ID

**Type**: `string`  
**Default**: None  
**Required**: Only if streaming responses are enabled

**Description**: Google Cloud Project ID for PubSub messaging (may differ from GCLOUD_PROJECT_ID).

**Impact**: Enables streaming of real-time responses to clients via PubSub.

### PUBSUB_TOPIC_NAME

**Type**: `string`  
**Default**: `book-finder-responses`  
**Required**: Only if streaming is enabled

**Description**: PubSub topic name for publishing streaming responses.

**Example**:
```bash
PUBSUB_TOPIC_NAME=book-finder-prod-responses
```

---

## Application Configuration

### FLASK_ENV

**Type**: `string`  
**Default**: `development`  
**Valid Values**: `development`, `production`  
**Required**: No

**Description**: Flask application environment.

**Impact**:
- `development`: Enables auto-reload, debug mode, verbose error messages
- `production`: Disables debug mode, uses production error handling

**Recommendation**: Always set to `production` for production deployments.

### SECRET_KEY

**Type**: `string`  
**Default**: `dev-secret-key-change-in-production`  
**Required**: Yes (for session security)

**Description**: Flask secret key for session encryption and CSRF protection.

**Security Requirements**:
- Must be 32+ characters
- Must be random and unique per deployment
- Never hardcode or commit to Git

**Generate a new secret**:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### PORT

**Type**: `integer`  
**Default**: `5000`  
**Valid Range**: 1024-65535  
**Required**: No

**Description**: HTTP port the agent listens on.

**Impact**: Must match the port exposed in Dockerfile and Kubernetes Service.

**Example**:
```bash
PORT=8080  # Non-standard port
```

### LOG_LEVEL

**Type**: `string`  
**Default**: `INFO`  
**Valid Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`  
**Required**: No

**Description**: Minimum logging level for the application.

**Impact**:
- `DEBUG`: Very verbose, includes all SQL queries and API calls (high disk I/O)
- `INFO`: Standard production level, logs major events
- `WARNING`: Only warnings and errors

**Recommendation**: Use `INFO` for production, `DEBUG` for troubleshooting.

---

## Gunicorn (Production Server) Configuration

### WORKER_COUNT

**Type**: `integer`  
**Default**: `4`  
**Valid Range**: 1-32  
**Recommended Formula**: `(2 × CPU_COUNT) + 1`  
**Required**: No

**Description**: Number of Gunicorn worker processes.

**Impact**: 
- Higher = better concurrency, higher memory usage
- Lower = lower memory, but fewer concurrent requests handled

**Tuning**:
```bash
# For 2-core machine
WORKER_COUNT=5      # (2 × 2) + 1

# For 4-core machine
WORKER_COUNT=9      # (2 × 4) + 1

# For 8-core machine
WORKER_COUNT=17     # (2 × 8) + 1
```

### WORKER_THREADS_COUNT

**Type**: `integer`  
**Default**: `2`  
**Valid Range**: 1-10  
**Required**: No

**Description**: Number of threads per worker process (with gthread worker class).

**Impact**: Enables concurrent request handling within each worker.

**Total Concurrent Requests**: `WORKER_COUNT × WORKER_THREADS_COUNT`

**Tuning**:
```bash
# For high concurrency
WORKER_THREADS_COUNT=4  # 4 workers × 4 threads = 16 concurrent

# For low memory
WORKER_THREADS_COUNT=1  # 4 workers × 1 thread = 4 concurrent
```

### WORKER_TIMEOUT

**Type**: `integer` (seconds)  
**Default**: `120`  
**Valid Range**: 30-600  
**Required**: No

**Description**: Timeout for worker processes before being killed and restarted.

**Impact**: Prevents hung workers from blocking requests indefinitely.

**Tuning**:
```bash
WORKER_TIMEOUT=60    # Shorter timeout for responsive API
WORKER_TIMEOUT=300   # Longer timeout for slow queries
```

### MAX_REQUEST_TO_WORKER_RESTART

**Type**: `integer`  
**Default**: `1000`  
**Valid Range**: 100-10000  
**Required**: No

**Description**: Number of requests before a worker is recycled (killed and restarted).

**Impact**: Mitigates gradual memory leaks in Python processes.

**Tuning**:
```bash
MAX_REQUEST_TO_WORKER_RESTART=1000  # Restart every 1000 requests
MAX_REQUEST_TO_WORKER_RESTART=500   # More frequent restarts for high memory usage
```

### WORKER_GRACEFUL_TIMEOUT

**Type**: `integer` (seconds)  
**Default**: `30`  
**Valid Range**: 10-120  
**Required**: No

**Description**: Time to gracefully shut down workers during restart/reload.

**Impact**: Allows in-flight requests to complete before killing the process.

---

## LLM Configuration

### LLM_MODEL_NAME

**Type**: `string`  
**Default**: `gemini-2.0-flash-001`  
**Valid Values**: Vertex AI model names  
**Required**: Yes (if generating responses)

**Description**: LLM model to use for response generation.

**Available Models**:
- `gemini-2.0-flash-001`: Latest, fastest, low cost
- `gemini-1.5-pro`: Higher quality, more expensive
- `gemini-1.5-flash`: Balanced quality and speed

**Example**:
```bash
LLM_MODEL_NAME=gemini-2.0-flash-001
```

### LLM_TEMPERATURE

**Type**: `float`  
**Default**: `0.7`  
**Valid Range**: 0.0-2.0  
**Required**: No

**Description**: Controls randomness in LLM outputs.

**Impact**:
- 0.0: Deterministic, always same output (good for facts)
- 0.7: Balanced (default)
- 1.5+: More creative, varied outputs

**Tuning**:
```bash
LLM_TEMPERATURE=0.3  # For factual book summaries
LLM_TEMPERATURE=0.7  # For conversational responses
LLM_TEMPERATURE=1.2  # For creative recommendations
```

### LLM_MAX_TOKENS

**Type**: `integer`  
**Default**: `1024`  
**Valid Range**: 10-8000  
**Required**: No

**Description**: Maximum tokens (words) in LLM response.

**Impact**: Affects response length and cost.

**Tuning**:
```bash
LLM_MAX_TOKENS=512   # Shorter responses
LLM_MAX_TOKENS=2048  # Longer, more detailed responses
```

### LLM_TOP_P

**Type**: `float`  
**Default**: `0.95`  
**Valid Range**: 0.0-1.0  
**Required**: No

**Description**: Nucleus sampling parameter for controlling output diversity.

**Impact**: 
- Lower values = more focused outputs
- Higher values = more diverse outputs

### ENABLE_STREAMING

**Type**: `boolean`  
**Default**: `true`  
**Valid Values**: `true`, `false`  
**Required**: No

**Description**: Enable streaming LLM responses to clients.

**Impact**: If enabled, responses are streamed to PubSub as they're generated (lower latency perception).

---

## Retrieval Configuration

### BOOKS_PER_RESULT

**Type**: `integer`  
**Default**: `5`  
**Valid Range**: 1-50  
**Required**: No

**Description**: Number of top-ranked books to include in the final response.

**Impact**: Affects context size for LLM and response latency.

**Tuning**:
```bash
BOOKS_PER_RESULT=3   # Minimal context, fast
BOOKS_PER_RESULT=10  # More comprehensive, slower
```

### SIMILARITY_THRESHOLD

**Type**: `float`  
**Default**: `0.3`  
**Valid Range**: 0.0-1.0  
**Required**: No

**Description**: Minimum cosine similarity score for book content chunks (0.0-1.0 scale).

**Impact**: 
- Higher threshold = stricter matching, fewer results
- Lower threshold = loose matching, more results

**Tuning**:
```bash
SIMILARITY_THRESHOLD=0.2  # Very inclusive, high recall
SIMILARITY_THRESHOLD=0.5  # Balanced
SIMILARITY_THRESHOLD=0.7  # Very strict, high precision
```

### FILTER_SIMILARITY_THRESHOLD

**Type**: `float`  
**Default**: `0.65`  
**Valid Range**: 0.0-1.0  
**Required**: No

**Description**: Minimum similarity for attribute-based filters (authors, genres, etc.).

**Impact**: Controls strictness of filter matching (e.g., finding books by a specific author).

### MAX_BOOK_IDS

**Type**: `integer`  
**Default**: `300`  
**Valid Range**: 1-1000  
**Required**: No

**Description**: Maximum total number of unique books to retrieve across all filters.

**Impact**: 
- Limits database load and memory usage
- Affects coverage and recall of search results

**Tuning**:
```bash
MAX_BOOK_IDS=100   # Strict limit, fast
MAX_BOOK_IDS=500   # Comprehensive search, slower
```

### MAX_CHUNKS_TO_USE

**Type**: `integer`  
**Default**: `6`  
**Valid Range**: 1-20  
**Required**: No

**Description**: Maximum number of text chunks (excerpts) to fetch per book.

**Impact**: Affects context richness and LLM context window usage.

### DEFAULT_SHOW_MORE_LENGTH

**Type**: `integer`  
**Default**: `3`  
**Valid Range**: 1-20  
**Required**: No

**Description**: Default number of books to return in "show more" pagination requests.

**Impact**: Controls pagination page size when users ask for more results.

### MAX_SHOW_MORE_BOOKS

**Type**: `integer`  
**Default**: `20`  
**Valid Range**: 5-100  
**Required**: No

**Description**: Maximum total books to store in pagination context per session.

**Impact**: Limits database storage for session state; older books are discarded.

---

## Scoring Configuration

### CONTEXT_WEIGHT_SCORE

**Type**: `float`  
**Default**: `0.45`  
**Valid Range**: 0.0-1.0  
**Constraint**: Must sum to 1.0 with DOCUMENT_WEIGHT_SCORE + KEYWORD_WEIGHT_SCORE  
**Required**: No

**Description**: Weight for semantic similarity scoring component.

**Formula**: `Final Score = (0.45 × S_sim) + (0.25 × S_doc) + (0.30 × S_key)`

**Impact**: Higher weight = semantic similarity has more influence on ranking.

### DOCUMENT_WEIGHT_SCORE

**Type**: `float`  
**Default**: `0.25`  
**Valid Range**: 0.0-1.0  
**Constraint**: Must sum to 1.0 with other weights  
**Required**: No

**Description**: Weight for document overlap/filter density scoring.

**Impact**: Higher weight = books matching more filters rank higher.

### KEYWORD_WEIGHT_SCORE

**Type**: `float`  
**Default**: `0.30`  
**Valid Range**: 0.0-1.0  
**Constraint**: Must sum to 1.0 with other weights  
**Required**: No

**Description**: Weight for keyword/n-gram frequency scoring.

**Impact**: Higher weight = books with matching keywords rank higher.

### Validation

The agent validates that scoring weights sum to 1.0 (±0.01 tolerance) at startup:

```bash
# Valid
CONTEXT_WEIGHT_SCORE=0.45
DOCUMENT_WEIGHT_SCORE=0.25
KEYWORD_WEIGHT_SCORE=0.30
# Sum = 1.0 ✓

# Invalid
CONTEXT_WEIGHT_SCORE=0.5
DOCUMENT_WEIGHT_SCORE=0.3
KEYWORD_WEIGHT_SCORE=0.3
# Sum = 1.1 ✗ Agent will refuse to start
```

---

## Table Names Configuration

### SESSION_CONTEXT_TABLE

**Type**: `string`  
**Default**: `book_retrieved_document_details`  
**Required**: No

**Description**: Name of the PostgreSQL table for storing session context and pagination state.

**Impact**: Must exist in the database before the agent starts.

### BOOK_SUMMARY_TABLE

**Type**: `string`  
**Default**: `book_summary_backup_2`  
**Required**: No

**Description**: PostgreSQL table containing book summary information.

### BOOK_CONTENT_TABLE

**Type**: `string`  
**Default**: `book_content_chunked_backup_2`  
**Required**: No

**Description**: PostgreSQL table containing chunked book content for semantic search.

### BOOK_METADATA_TABLE

**Type**: `string`  
**Default**: `book_metadata_backup_2`  
**Required**: No

**Description**: PostgreSQL table containing book metadata.

---

## Citation and Verification Configuration

### MAX_WORKERS_FOR_CITATION_GENERATION

**Type**: `integer`  
**Default**: `10`  
**Valid Range**: 1-50  
**Required**: No

**Description**: Number of parallel threads for verifying citations against source texts.

**Impact**: 
- Higher = faster verification, higher CPU/memory usage
- Lower = slower verification, lower resource usage

**Tuning**:
```bash
MAX_WORKERS_FOR_CITATION_GENERATION=5   # Conservative
MAX_WORKERS_FOR_CITATION_GENERATION=10  # Balanced (default)
MAX_WORKERS_FOR_CITATION_GENERATION=20  # Aggressive
```

### CITATION_VERIFICATION_RETRY_ATTEMPTS

**Type**: `integer`  
**Default**: `1`  
**Valid Range**: 0-3  
**Required**: No

**Description**: Number of times to retry citation verification before marking as failed.

**Impact**: Retries can catch transient failures but increase latency.

---

## Configuration Validation

### Automatic Validation at Startup

The agent automatically validates configuration on startup:

```bash
python -c "import Config; Config.validate_configuration()"
```

**Checked Items**:
1. ✓ All required variables are set (POSTGRES_HOST, GCLOUD_PROJECT_ID, etc.)
2. ✓ Scoring weights sum to 1.0 (±0.01)
3. ✓ Numeric values are within valid ranges
4. ✓ Database connectivity (attempted)
5. ✓ GCP credentials validity

### Manual Validation

Validate specific parameters:

```python
import os
from Config import validate_configuration

try:
    validate_configuration()
    print("✓ All configuration valid")
except ConfigError as e:
    print(f"✗ Configuration error: {e}")
```

---

## Environment File Template

Complete `.env` file template:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=book_finder_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change_me_in_production

# Google Cloud
GCLOUD_PROJECT_ID=your-gcp-project
GCLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
PUBSUB_PROJECT_ID=your-gcp-project
PUBSUB_TOPIC_NAME=book-finder-responses

# Application
FLASK_ENV=development
SECRET_KEY=change-this-to-a-random-secret
PORT=5000
LOG_LEVEL=INFO

# Gunicorn
WORKER_COUNT=4
WORKER_THREADS_COUNT=2
WORKER_TIMEOUT=120
MAX_REQUEST_TO_WORKER_RESTART=1000
WORKER_GRACEFUL_TIMEOUT=30

# LLM
LLM_MODEL_NAME=gemini-2.0-flash-001
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=1024
LLM_TOP_P=0.95
ENABLE_STREAMING=true

# Retrieval
BOOKS_PER_RESULT=5
SIMILARITY_THRESHOLD=0.3
FILTER_SIMILARITY_THRESHOLD=0.65
MAX_BOOK_IDS=300
MAX_CHUNKS_TO_USE=6
DEFAULT_SHOW_MORE_LENGTH=3
MAX_SHOW_MORE_BOOKS=20

# Scoring
CONTEXT_WEIGHT_SCORE=0.45
DOCUMENT_WEIGHT_SCORE=0.25
KEYWORD_WEIGHT_SCORE=0.30

# Table Names
SESSION_CONTEXT_TABLE=book_retrieved_document_details
BOOK_SUMMARY_TABLE=book_summary_backup_2
BOOK_CONTENT_TABLE=book_content_chunked_backup_2
BOOK_METADATA_TABLE=book_metadata_backup_2

# Citation
MAX_WORKERS_FOR_CITATION_GENERATION=10
```

---

## Configuration Best Practices

### Local Development

```bash
FLASK_ENV=development
LOG_LEVEL=DEBUG
SIMILARITY_THRESHOLD=0.2  # Inclusive for testing
MAX_BOOK_IDS=50            # Limited for speed
```

### Production

```bash
FLASK_ENV=production
LOG_LEVEL=INFO
SIMILARITY_THRESHOLD=0.5   # Stricter for quality
MAX_BOOK_IDS=300           # Full capability
WORKER_COUNT=9             # High concurrency
```

### High-Performance

```bash
BOOKS_PER_RESULT=3         # Minimal context
MAX_CHUNKS_TO_USE=3        # Fewer chunks
MAX_WORKERS_FOR_CITATION_GENERATION=20
WORKER_THREADS_COUNT=4
WORKER_TIMEOUT=60
```

### Cost-Optimized

```bash
LLM_MAX_TOKENS=512         # Shorter responses
BOOKS_PER_RESULT=3         # Fewer books
SIMILARITY_THRESHOLD=0.6   # Stricter matching
WORKER_COUNT=2             # Minimal workers
```

---

## Support

For configuration issues:

1. Check this reference document
2. Run validation: `python -c "import Config; Config.validate_configuration()"`
3. Review DEVELOPER_GUIDE.md Troubleshooting section
4. Check application logs: `docker-compose logs -f book-finder-agent`

