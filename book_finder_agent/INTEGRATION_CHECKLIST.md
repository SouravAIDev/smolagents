# Book Finder Agent — Integration Checklist

Complete pre-deployment verification checklist for the Book Finder Agent. Use this to ensure all components are properly integrated and the system is ready for production.

**Date**: ________________  
**Checked By**: ________________  
**Environment**: [ ] Development [ ] Staging [ ] Production  

---

## A. Module Imports and Dependencies

### A1. Core Agent Module

- [ ] `BookFinderAgent` class imports from `RecommendationAgentBase`
- [ ] `BookFinderAgent` defines `CONFIG_CLASS = BookFinderAgentSetup`
- [ ] `BookFinderAgent.setup()` method initializes all required tools
- [ ] `BookFinderAgent.run()` method is decorated with `@AITrace(BookFinderAgentTrace)`
- [ ] All filter enum values are imported from `BookFinderFilterType`

**Verification Command**:
```bash
python -c "from book_finder_agent.book_finder_agent import BookFinderAgent; print('✓ BookFinderAgent imports successfully')"
```

### A2. Configuration Classes

- [ ] `BookFinderAgentSetup` extends `AgentSetupBase`
- [ ] All required fields are defined with proper types and defaults
- [ ] `BookFinderAgentSetup` includes:
  - [ ] Fallback response configuration
  - [ ] Retrieval parameters (similarity_threshold, max_chunks, etc.)
  - [ ] Scoring weights (context, document, keyword)
  - [ ] Table names configuration
  - [ ] LLM parameters
  - [ ] Pagination configuration

**Verification Command**:
```bash
python -c "from book_finder_agent.book_finder_agent_setup import BookFinderAgentSetup; print(BookFinderAgentSetup.model_json_schema())"
```

### A3. Trace Schema

- [ ] `BookFinderAgentTrace` extends `AgentsTraceBase`
- [ ] Trace includes all observable execution fields:
  - [ ] `user_query`
  - [ ] `active_filters`
  - [ ] `retrieved_books`
  - [ ] `citations`
  - [ ] `final_response`
  - [ ] `error_state`
  - [ ] `session_id`

**Verification Command**:
```bash
python -c "from book_finder_agent.book_finder_agent_trace import BookFinderAgentTrace; t = BookFinderAgentTrace(); print(f'Trace fields: {t.model_fields.keys()}')"
```

### A4. Helper Modules

- [ ] `BookFinderFilterType` enum is properly defined with all 14 filter types
- [ ] `FILTER_TABLE_MAPPING` maps each filter type to a `FilterDetails` configuration
- [ ] `BookFinderUtilities` provides normalization functions
- [ ] `DatabaseRetrievalUtils` is imported and available
- [ ] `CitationUtils` is imported for citation processing

**Verification Command**:
```bash
python -c "from book_finder_agent.book_finder_helpers import BookFinderFilterType, FILTER_TABLE_MAPPING; print(f'Filters: {len(BookFinderFilterType.__members__)}'); print(f'Mappings: {len(FILTER_TABLE_MAPPING)}')"
```

---

## B. Tool Registration and Initialization

### B1. SQL Executor Tool

- [ ] Tool is imported: `from llm_studio_tools.sql_executor_tool import SQLExecutorTool`
- [ ] Tool is registered in `get_setup_config()` return value
- [ ] Tool configuration is processed via `process_config()`
- [ ] Tool instance is created in `setup()` method
- [ ] Tool is stored as `self.sql_executor_tool`
- [ ] Tool configuration includes database connection parameters

**Verification Command**:
```bash
python -c "from book_finder_agent.book_finder_agent import BookFinderAgent; config = BookFinderAgent.get_setup_config(); print(f'Tools in config: {list(config.get(\"tools\", {}).keys())}')"
```

### B2. LLM Configuration Tool

- [ ] Tool is imported: `from llm_studio_tools.llm_configuration_tool import LLMConfigurationTool`
- [ ] Tool is registered in agent configuration
- [ ] Tool is initialized in `setup()` with proper config
- [ ] Deepcopy of tool config is stored for restoration: `self.llm_config_tool_copy`
- [ ] Tool supports context setting for system prompts
- [ ] Tool supports streaming (if enabled)

**Verification Command**:
```bash
python -c "from llm_studio_tools.llm_configuration_tool import LLMConfigurationTool; print('✓ LLMConfigurationTool imports successfully')"
```

### B3. Semantic Similarity Tool

- [ ] Tool is imported: `from tools.semantic_similarity_tool import SemanticSimilarityTool`
- [ ] Tool is initialized in `setup()` with embedding configuration
- [ ] Tool can generate embeddings via `run(text=...)`
- [ ] Embedding dimensions match configuration (default: 1536)
- [ ] Tool uses Google Vertex AI for embeddings

**Verification Command**:
```bash
python -c "from book_finder_agent.tools.semantic_similarity_tool import SemanticSimilarityTool; print('✓ SemanticSimilarityTool imports successfully')"
```

### B4. Citation Tool

- [ ] Tool is imported: `from tools.citation_tool import CitationTool`
- [ ] Tool is initialized in `setup()`
- [ ] Tool configuration includes max_workers setting
- [ ] Tool configuration includes retry_attempts
- [ ] Tool provides parallel verification capability

**Verification Command**:
```bash
python -c "from book_finder_agent.tools.citation_tool import CitationTool; print('✓ CitationTool imports successfully')"
```

---

## C. SQL Templates and Database Setup

### C1. Query Files Directory

- [ ] `queries/` directory exists in agent folder
- [ ] All 10 required SQL files are present:
  - [ ] `retrieve_book_vector_search.sql`
  - [ ] `retrieve_book_chunks.sql`
  - [ ] `create_session_context_table.sql`
  - [ ] `fetch_show_more_books.sql`
  - [ ] `fetch_latest_question_for_session.sql`
  - [ ] `mark_books_as_displayed.sql`
  - [ ] `insert_retrieved_documents.sql`
  - [ ] `expire_old_context.sql`
  - [ ] `filter_query_with_metadata.sql`
  - [ ] `fallback_fetch_show_more_books.sql` (for pagination fallback)

**Verification Command**:
```bash
ls -la book_finder_agent/queries/*.sql | wc -l
```

### C2. SQL Template Loading

- [ ] `_read_queries()` method loads all SQL templates
- [ ] Queries are stored in `self.queries` dictionary
- [ ] Missing query files log warnings but don't crash startup
- [ ] Query templates support format placeholders (e.g., `{table_name}`)

**Verification Command**:
```bash
python -c "from book_finder_agent.book_finder_database_retrieval import DatabaseRetrievalUtils; import os; os.chdir('book_finder_agent'); utils = DatabaseRetrievalUtils; queries = utils._read_queries(None); print(f'Loaded {len(queries)} queries')"
```

### C3. Database Connectivity

- [ ] PostgreSQL/AlloyDB server is running
- [ ] Database credentials are set in environment variables
- [ ] Test connection succeeds:
  ```bash
  psql -U $POSTGRES_USER -h $POSTGRES_HOST -d $POSTGRES_DB -c "SELECT 1;"
  ```
- [ ] pgvector extension is installed: `CREATE EXTENSION IF NOT EXISTS vector;`
- [ ] Required tables exist:
  - [ ] `book_summary_backup_2`
  - [ ] `book_content_chunked_backup_2`
  - [ ] `book_metadata_backup_2`
  - [ ] `book_contributors_backup_2`
  - [ ] `book_audience_backup_2`
  - [ ] `geo_location_backup_2`
  - [ ] `book_notable_quotes_backup_2`
  - [ ] `book_notable_characters_backup_2`
  - [ ] `book_content_sections_backup_2`
  - [ ] `book_imprint_details_backup_2`
  - [ ] `book_publishers_backup_2`
  - [ ] `book_prize_details_backup_2`

### C4. Session Context Table

- [ ] Table `book_retrieved_document_details` is created (auto-created on first run)
- [ ] Table has required columns:
  - [ ] `id` (SERIAL PRIMARY KEY)
  - [ ] `session_id` (VARCHAR)
  - [ ] `question` (TEXT)
  - [ ] `isbn` (VARCHAR)
  - [ ] `context_score` (FLOAT)
  - [ ] `is_displayed` (BOOLEAN)
  - [ ] `is_expired` (BOOLEAN)
  - [ ] `display_count` (INTEGER)
  - [ ] `chunk_ids` (TEXT)
  - [ ] `created_at` (TIMESTAMP)
  - [ ] `updated_at` (TIMESTAMP)
- [ ] Required indices exist:
  - [ ] `idx_session_question_expired` (for pagination queries)
  - [ ] `idx_session_displayed` (for filtering)
  - [ ] `idx_context_score` (for sorting)

**Verification Command**:
```bash
psql -U $POSTGRES_USER -h $POSTGRES_HOST -d $POSTGRES_DB -c "\d book_retrieved_document_details;"
```

### C5. Vector Indices

- [ ] All required tables have HNSW indices on vector columns
- [ ] Vector columns are type `VECTOR(1536)`
- [ ] Indices use cosine distance operator (`<->`)
- [ ] Indices are named meaningfully (e.g., `idx_book_summary_embedding`)

**Verification Command**:
```bash
psql -U $POSTGRES_USER -h $POSTGRES_HOST -d $POSTGRES_DB -c "SELECT * FROM pg_indexes WHERE schemaname = 'public' AND tablename LIKE '%backup%';"
```

---

## D. Configuration and Environment

### D1. Environment Variables

- [ ] `.env` file exists in project root
- [ ] All critical variables are set:
  - [ ] `POSTGRES_HOST`
  - [ ] `POSTGRES_PORT`
  - [ ] `POSTGRES_DB`
  - [ ] `POSTGRES_USER`
  - [ ] `POSTGRES_PASSWORD`
  - [ ] `GCLOUD_PROJECT_ID`
  - [ ] `GOOGLE_APPLICATION_CREDENTIALS`
  - [ ] `GCLOUD_LOCATION`
  - [ ] `LLM_MODEL_NAME`
  - [ ] `FLASK_ENV` (set to `production` for prod)
  - [ ] `SECRET_KEY` (unique, 32+ characters)
  - [ ] `PORT`
  - [ ] `LOG_LEVEL`

**Verification Command**:
```bash
python -c "import Config; Config.validate_configuration(); print('✓ All required environment variables are set')"
```

### D2. Configuration Validation

- [ ] Scoring weights sum to 1.0 (±0.01): `context + document + keyword = 1.0`
- [ ] All numeric parameters are within valid ranges
- [ ] Database connection test succeeds
- [ ] GCP credentials file exists and is readable
- [ ] No hardcoded secrets in code

**Verification Command**:
```bash
python -c "import Config; Config.validate_configuration(); print('✓ Configuration validation passed')"
```

### D3. Google Cloud Setup

- [ ] Service account key is downloaded from GCP Console
- [ ] Service account has required roles:
  - [ ] `Vertex AI User` (for LLM calls)
  - [ ] `Vertex AI Workbench User` (for embeddings)
  - [ ] `Cloud Logging Admin` (for logging)
  - [ ] `Pub/Sub Publisher` (if streaming is enabled)
- [ ] `GOOGLE_APPLICATION_CREDENTIALS` environment variable points to valid key file
- [ ] GCP project ID matches `GCLOUD_PROJECT_ID`

**Verification Command**:
```bash
python -c "from google.oauth2 import service_account; import os; creds = service_account.Credentials.from_service_account_file(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')); print(f'✓ GCP credentials valid for project: {creds.project_id}')"
```

---

## E. Agent Initialization

### E1. Agent Class Setup

- [ ] `BookFinderAgent` class can be instantiated: `agent = BookFinderAgent()`
- [ ] `setup()` method completes without errors
- [ ] `setup()` returns an empty dict (standard contract)
- [ ] All tools are initialized (no None values)
- [ ] SQL queries are loaded into `self.queries`

**Verification Command**:
```bash
python -c "
from book_finder_agent.book_finder_agent import BookFinderAgent
import Config
from llm_studio_agents.utils.utils import process_config

agent = BookFinderAgent()
config = process_config({}, sub_level='tools')  # Empty config for testing
result = agent.setup(config=config, data={})
assert result == {}, 'setup() should return empty dict'
print('✓ Agent initializes successfully')
"
```

### E2. Tool State Preservation

- [ ] Original SQL tool headers are snapshotted: `self.original_sql_start_header_messages`
- [ ] Original SQL tool format columns are snapshotted
- [ ] Tools are restored after each request
- [ ] No shared state persists between requests

**Verification Command**:
```bash
python -c "
from book_finder_agent.book_finder_agent import BookFinderAgent
agent = BookFinderAgent()
assert hasattr(agent, 'original_sql_start_header_messages')
assert hasattr(agent, 'original_sql_end_header_messages')
assert hasattr(agent, 'original_format_columns')
print('✓ Tool state preservation configured')
"
```

### E3. Filter Registry Initialization

- [ ] `FILTER_TABLE_MAPPING` is loaded in `setup()`
- [ ] Filter table mapping is accessible: `app.config['BOOK_FILTER_TABLE_MAPPING']`
- [ ] All 14 filter types have corresponding table mappings
- [ ] Each filter has a `FilterDetails` object with:
  - [ ] `table` (database table name)
  - [ ] `search_column` (column to search in)
  - [ ] `return_column` (column to return)
  - [ ] `select_columns` (list of columns to fetch)
  - [ ] `similarity_threshold` (if vector search)

**Verification Command**:
```bash
python -c "
from book_finder_agent.book_finder_helpers import FILTER_TABLE_MAPPING, BookFinderFilterType
assert len(FILTER_TABLE_MAPPING) == len(BookFinderFilterType.__members__), 'All filters must have mappings'
for filter_type, filter_details in FILTER_TABLE_MAPPING.items():
    assert hasattr(filter_details, 'table'), f'{filter_type} missing table'
    assert hasattr(filter_details, 'search_column'), f'{filter_type} missing search_column'
print(f'✓ All {len(FILTER_TABLE_MAPPING)} filters are properly mapped')
"
```

---

## F. Response Contract Validation

### F1. Response Shape Verification

- [ ] Agent returns exactly a 4-tuple:
  ```python
  (response_text: str, retrieved_books: list, citations: list, bypass_orchestrator_response: bool)
  ```
- [ ] `response_text` is always a non-empty string (never None)
- [ ] `retrieved_books` is always a list (may be empty)
- [ ] `citations` is always a list (may be empty)
- [ ] `bypass_orchestrator_response` is always a boolean
- [ ] On error, agent returns fallback response instead of raising exception

**Verification Command**:
```bash
python -c "
from book_finder_agent.book_finder_agent import BookFinderAgent
from llm_studio_agents.utils.utils import process_config

agent = BookFinderAgent()
config = process_config({}, sub_level='tools')
agent.setup(config=config, data={'session_id': 'test'})

# Test with empty query (should return fallback)
result = agent.run(user_query='', next_trace={}, trace={})
assert isinstance(result, dict)
assert 'response_text' in result
assert 'retrieved_books' in result
assert 'citations' in result
assert 'bypass_orchestrator_response' in result
print('✓ Response shape matches contract')
"
```

### F2. Fallback Response Verification

- [ ] Fallback response is defined in configuration
- [ ] Fallback response is returned on error
- [ ] Fallback response is returned when no books are found
- [ ] Fallback response is not None and not empty

**Verification Command**:
```bash
python -c "
from book_finder_agent.book_finder_agent_setup import BookFinderAgentSetup
config = BookFinderAgentSetup()
assert config.fallback_response is not None
assert len(config.fallback_response) > 0
print(f'✓ Fallback response configured: {config.fallback_response}')
"
```

---

## G. End-to-End Testing

### G1. Agent Health Check

- [ ] Start the agent: `python run.py`
- [ ] Health check endpoint responds:
  ```bash
  curl http://localhost:5000/utility/book-content-rag-agent/health
  ```
- [ ] Response status: 200 OK
- [ ] Response body contains `{"status": "healthy"}`

### G2. Configuration Endpoints

- [ ] GET `/get_config` returns agent configuration schema
- [ ] GET `/get_llm_config` returns LLM-specific configuration
- [ ] Both endpoints return valid JSON
- [ ] Configuration includes all required fields

**Test Command**:
```bash
curl http://localhost:5000/utility/book-content-rag-agent/get_config | python -m json.tool
```

### G3. Simple Prediction Request

- [ ] Send test request to `/prediction` endpoint
- [ ] Request includes all required fields:
  ```json
  {
    "agent_id": "test",
    "session_id": "test-session",
    "concierge_id": "test",
    "question": "Find books about science",
    "agent_arguments": {
      "user_query": "Find books about science"
    }
  }
  ```
- [ ] Response status: 200 OK (not 500)
- [ ] Response body contains all required fields: `response`, `agent_guide`, `sources`, `trace`, `bypass_orchestrator_response`
- [ ] `response` field is non-empty string
- [ ] No unhandled exceptions in logs

**Test Command**:
```bash
curl -X POST http://localhost:5000/utility/book-content-rag-agent/prediction \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"test","session_id":"test","concierge_id":"test","question":"test","agent_arguments":{"user_query":"test"}}'
```

### G4. Pagination Request (Flow B)

- [ ] Send request with `show_more_details` parameter
- [ ] Pagination retrieves previously stored results
- [ ] Retrieved books are marked as displayed
- [ ] Subsequent pagination requests return new books
- [ ] Response includes all required fields

### G5. Filtered Query Request (Flow C)

- [ ] Send request with filter parameters (e.g., `genre_details`, `contributor_details`)
- [ ] Agent applies filters to results
- [ ] Response includes only books matching filters
- [ ] Filter application works with JSONB metadata

### G6. Error Handling Verification

- [ ] Send invalid JSON: `{"invalid": "request"}`
- [ ] Response status: 400 Bad Request (not 500)
- [ ] Error message is descriptive
- [ ] Send empty user query: `{"user_query": ""}`
- [ ] Response status: 200 with fallback response (not crash)
- [ ] Send non-existent book query: `{"user_query": "xyzabc123nonexistent"}`
- [ ] Response status: 200 with fallback response

---

## H. Performance and Load Testing

### H1. Latency Baseline

- [ ] Simple request (without LLM generation) completes in < 5 seconds
- [ ] Request with LLM generation completes in < 30 seconds
- [ ] Database queries (vector search) complete in < 1 second
- [ ] Citation verification completes in < 10 seconds

### H2. Concurrent Requests

- [ ] Agent handles 3 concurrent requests without errors
- [ ] Agent handles 10 concurrent requests without resource exhaustion
- [ ] No request interference (session isolation works)
- [ ] Database connection pool does not exhaust

**Test Command**:
```bash
# Using Apache Bench
ab -n 10 -c 3 -p test_request.json -T application/json \
  http://localhost:5000/utility/book-content-rag-agent/prediction
```

### H3. Memory Usage

- [ ] Single instance uses < 500 MB RAM at idle
- [ ] Memory does not grow unboundedly with requests
- [ ] No obvious memory leaks (monitor for 5+ minutes under load)

**Test Command**:
```bash
ps aux | grep python
```

---

## I. Security Checklist

### I1. Credentials and Secrets

- [ ] No hardcoded passwords in code
- [ ] No credentials in `.env` file committed to Git (`.env` is in `.gitignore`)
- [ ] Secrets are stored in environment variables or secrets manager
- [ ] Google service account key is not committed
- [ ] `SECRET_KEY` is unique per deployment

### I2. Input Validation

- [ ] All user inputs are validated against schema
- [ ] SQL queries use parameterized statements (no injection)
- [ ] Database credentials are not logged
- [ ] User queries are not echoed in responses

### I3. Access Control

- [ ] Flask `CORS` is configured appropriately
- [ ] Health check endpoint is accessible without authentication
- [ ] Prediction endpoint requires valid request schema
- [ ] Database user has minimal required permissions (not superuser)

---

## J. Deployment Readiness

### J1. Docker Image

- [ ] `Dockerfile` exists and builds successfully
- [ ] Image size is < 500 MB
- [ ] Image runs as non-root user
- [ ] Health check is configured in image
- [ ] No secrets are embedded in image

### J2. Kubernetes Manifests

- [ ] Deployment YAML is syntactically valid
- [ ] Service YAML is syntactically valid
- [ ] Ingress YAML is syntactically valid (if used)
- [ ] Secrets are created separately (not in manifests)
- [ ] ConfigMap includes all non-sensitive configuration
- [ ] Resource limits are defined (CPU, memory)
- [ ] Health probes are configured (liveness, readiness)

### J3. Documentation

- [ ] `DEVELOPER_GUIDE.md` is complete and accurate
- [ ] `DEPLOYMENT_GUIDE.md` is complete and tested
- [ ] `QUICKSTART.md` is verified to work
- [ ] `CONFIG_REFERENCE.md` documents all parameters
- [ ] API documentation is available and accurate

---

## Checklist Sign-Off

**All items verified**: [ ] YES [ ] NO

**Date completed**: ________________

**Verified by**: ________________

**Notes/Issues Found**:
```



```

**Recommended Actions**:
```



```

---

## Next Steps

Once all items are checked:

1. ✓ Submit this completed checklist to the team
2. ✓ Address any failed items before production deployment
3. ✓ Follow the deployment guide: `DEPLOYMENT_GUIDE.md`
4. ✓ Set up monitoring and alerting per `DEPLOYMENT_GUIDE.md` section on health checks
5. ✓ Configure logging and observability for production
6. ✓ Schedule post-deployment review meeting

For questions, refer to:
- **Configuration issues**: `CONFIG_REFERENCE.md`
- **Setup issues**: `DEVELOPER_GUIDE.md`
- **Deployment issues**: `DEPLOYMENT_GUIDE.md`
- **Rapid setup**: `QUICKSTART.md`

