# Book Finder Agent - Module Integration Guide

## Overview

This document details how all modules from ACT-1 through ACT-13 integrate to form a complete, functional Book Finder Agent. Each section maps modules to their parent ACT and explains their role in the overall request flow.

## Dependency Graph

```
run.py (ACT-2)
  ├─ Config.py (ACT-13)
  │   ├─ Environment variable validation
  │   └─ Global configuration constants
  ├─ book_finder_helpers.py (ACT-3)
  │   ├─ BookFinderFilterType enum
  │   ├─ FilterTypeSchema validation
  │   ├─ BookFinderRequestSchema validation
  │   └─ FILTER_TABLE_MAPPING registry
  └─ BookFinderAgent (ACT-9, ACT-10, ACT-11, ACT-12)
      ├─ RecommendationAgentBase.py (ACT-13)
      │   └─ Base class setup(), error handling, response tuple assembly
      ├─ BookFinderAgentSetup (ACT-9)
      │   └─ Pydantic configuration schema
      ├─ BookFinderAgentTrace (ACT-9)
      │   └─ Trace schema for observability
      ├─ Tools (from llm-studio-tools)
      │   ├─ SQLExecutorTool
      │   ├─ LLMConfigurationTool
      │   ├─ SemanticSimilarityTool
      │   └─ CitationTool
      ├─ book_finder_database_retrieval.py (ACT-10)
      │   ├─ DatabaseRetrievalUtils
      │   ├─ Vector search execution
      │   ├─ Session management
      │   └─ Pagination state
      ├─ book_finder_session_helpers.py (ACT-10)
      │   ├─ Flow determination (A/B/C)
      │   ├─ Pagination state management
      │   ├─ Metadata filter application
      │   └─ Citation extraction
      ├─ book_finder_utilities.py (ACT-10)
      │   ├─ ISBN normalization
      │   ├─ UUID normalization
      │   ├─ Keyword scoring
      │   └─ Data normalization
      ├─ book_finder_citation_helpers.py (ACT-10)
      │   ├─ Citation regex extraction
      │   ├─ Substring verification
      │   └─ Citation stripping
      ├─ book_finder_llm_orchestration.py (ACT-11)
      │   ├─ XML context formatting
      │   ├─ LLM prompt building
      │   ├─ Response generation
      │   └─ Streaming updates
      ├─ book_finder_citation_verification.py (ACT-11)
      │   ├─ Citation extraction from response
      │   ├─ Parallel verification (ThreadPoolExecutor)
      │   ├─ Retry logic
      │   └─ Unverified citation stripping
      ├─ book_finder_response_assembly.py (ACT-11)
      │   ├─ Response tuple assembly
      │   ├─ Citation generation
      │   ├─ Retrieved documents formatting
      │   └─ Response validation
      ├─ book_finder_scoring_engine.py (ACT-12)
      │   ├─ Semantic similarity scoring
      │   ├─ Document overlap scoring
      │   ├─ Keyword frequency scoring
      │   └─ Weighted score combination
      ├─ book_finder_retrieval_orchestration.py (ACT-12)
      │   ├─ Parallel retrieval coordination
      │   ├─ IDs per filter calculation
      │   ├─ Content retrieval
      │   ├─ Post-processing
      │   └─ Score calculation
      ├─ book_finder_helpers.py (ACT-3)
      │   ├─ Request validation schemas
      │   └─ Filter mapping
      └─ utils/book_data_utils.py (ACT-13)
          ├─ Summary generation
          ├─ Data formatting
          ├─ Metadata extraction
          └─ Data normalization
```

## Request Flow Integration

### Flow A: Standard Semantic Retrieval

```
1. run.py:predict_api (ACT-2)
   ├─ Validates request with BookFinderRequestSchema (ACT-3)
   ├─ Constructs BookFinderAgent
   │
2. BookFinderAgent.setup() (ACT-9, ACT-13)
   ├─ Calls RecommendationAgentBase.setup()
   ├─ Initializes SQLExecutorTool, LLMConfigurationTool, etc.
   ├─ Loads SQL templates from queries/ (ACT-9)
   │
3. BookFinderAgent.run() (ACT-10, ACT-12)
   ├─ Determines flow = 'A' (standard)
   ├─ Calls _retrieve_ids() (ACT-12:RetrievalOrchestration)
   │  ├─ Executes vector search via DatabaseRetrievalUtils (ACT-10)
   │  ├─ Deduplicates results
   │  └─ Returns ISBN list
   ├─ Calls _retrieve_content() (ACT-12:RetrievalOrchestration)
   │  ├─ Fetches supporting chunks
   │  └─ Returns chunk data
   ├─ Calls _post_process() (ACT-12:RetrievalOrchestration)
   │  ├─ Normalizes data with book_data_utils.py (ACT-13)
   │  └─ Merges chunks with metadata
   ├─ Calls _calculate_scores() (ACT-12:ScoringEngine)
   │  ├─ Calculates semantic similarity score
   │  ├─ Calculates document overlap score
   │  ├─ Calculates keyword frequency score
   │  └─ Combines with configured weights (Config.py, ACT-13)
   │
4. Response Generation (ACT-11)
   ├─ BookFinderLLMOrchestration.prepare_context_block()
   │  └─ Formats ranked books as XML
   ├─ BookFinderLLMOrchestration.generate_response()
   │  ├─ Builds prompt with user query + context
   │  ├─ Calls LLMConfigurationTool.run()
   │  └─ Returns LLM response text
   ├─ send_streaming_response_to_pubsub() (ACT-11)
   │  └─ Sends interim updates
   │
5. Citation Verification (ACT-11)
   ├─ CitationVerificationEngine.extract_citations_from_response()
   │  ├─ Uses regex to find markdown citations
   │  └─ Returns citation list
   ├─ CitationVerificationEngine.verify_citations_parallel()
   │  ├─ Spawns ThreadPoolExecutor (max_workers from Config.py, ACT-13)
   │  ├─ For each citation:
   │  │  ├─ Extracts metadata (ISBN, page, etc.)
   │  │  ├─ Calls CitationTool.verify_substring()
   │  │  ├─ On failure: retries once
   │  │  └─ On persistent failure: marks unverified
   │  └─ Returns verification results
   ├─ CitationVerificationEngine.strip_unverified_citations()
   │  └─ Removes markdown links from unverified citations
   │
6. Response Assembly (ACT-11)
   ├─ ResponseAssembly.assemble_response_tuple()
   │  ├─ Formats retrieved books
   │  ├─ Generates citation objects via citation_generator()
   │  └─ Returns 4-tuple: (response_text, docs, citations, bypass_flag)
   │
7. Session Persistence (ACT-10)
   ├─ ShowMoreDetailsUtils._upsert_retrieved_documents()
   │  ├─ Stores ISBNs in session_context_table
   │  └─ Enables pagination (Flow B)
   │
8. Mark as Displayed (ACT-10)
   ├─ ShowMoreDetailsUtils.mark_books_as_displayed()
   │  └─ Updates is_displayed flag for returned books
   │
9. Return Response (ACT-2)
   └─ run.py:predict_api returns JSON with response, sources, trace
```

### Flow B: Pagination (Show More)

```
1-2. Same as Flow A (validate + setup)
   │
3. BookFinderAgent.run() detects show_more_details parameter
   ├─ Determines flow = 'B' (pagination)
   │
4. ShowMoreDetailsUtils._fetch_show_more_books() (ACT-10)
   ├─ Queries session_context_table for undisplayed books
   ├─ Uses session_id + question_id as key
   ├─ Returns previously_displayed_documents + new_documents
   │
5. Reformats retrieved books using book_data_utils (ACT-13)
   │
6. Remaining steps 4-9 are identical to Flow A
   └─ Citation verification, response assembly, persistence
```

### Flow C: Metadata Filtering

```
1-2. Same as Flow A (validate + setup)
   │
3. BookFinderAgent.run() detects metadata filters
   ├─ Determines flow = 'C' (filtered context)
   │
4. ShowMoreDetailsUtils._fetch_filtered_question_documents() (ACT-10)
   ├─ Queries session_context_table
   ├─ Applies JSONB filter on metadata
   ├─ Returns filtered results ordered by context_score
   │
5. Remaining steps are identical to Flow A
   └─ Citation verification, response assembly, persistence
```

### Convergence at A5: Response Assembly

```
     Flow A          Flow B          Flow C
  (Semantic)    (Pagination)    (Filtered)
       │              │              │
       └──────────────┴──────────────┘
                      ▼
         A5: Response Assembly
         ├─ LLM Generation (ACT-11)
         ├─ Citation Verification (ACT-11)
         ├─ Response Assembly (ACT-11)
         └─ Return 4-tuple
```

## Configuration Integration

### Config.py (ACT-13) provides all constants:

```python
# Loaded by run.py
app.config['DB_CONNECTION'] = DATABASE_URI  # From Config.POSTGRES_*

# Passed to BookFinderAgent via agent_config
agent.config.context_weight_score = CONTEXT_WEIGHT_SCORE      # 0.45
agent.config.document_weight_score = DOCUMENT_WEIGHT_SCORE    # 0.25
agent.config.keyword_weight_score = KEYWORD_WEIGHT_SCORE      # 0.30
agent.config.max_book_ids = MAX_BOOK_IDS                      # 300
agent.config.similarity_threshold = SIMILARITY_THRESHOLD      # 0.3
agent.config.llm_model_name = LLM_MODEL_NAME                  # gemini-2.0-flash-001

# Used by individual components
BookFinderLLMOrchestration uses: LLM_TEMPERATURE, LLM_MAX_TOKENS
ScoringEngine uses: CONTEXT_WEIGHT_SCORE, DOCUMENT_WEIGHT_SCORE, KEYWORD_WEIGHT_SCORE
DatabaseRetrievalUtils uses: MAX_CHUNKS_PER_BOOK, SESSION_CONTEXT_TABLE
CitationVerificationEngine uses: MAX_WORKERS_FOR_CITATION_GENERATION
```

## Tool Integration (from llm-studio-tools)

### SQLExecutorTool (ACT-10, ACT-12)

```python
# Initialized in BookFinderAgent.setup()
self.sql_executor_tool = SQLExecutorTool(config=sql_executor_config)

# Used in DatabaseRetrievalUtils._execute_query()
self.sql_executor_tool.run(
    sql_query=query_template.format(...),
    params=(param1, param2, ...),
    next_trace=next_trace,
    trace=trace
)
```

### LLMConfigurationTool (ACT-11)

```python
# Initialized in BookFinderAgent.setup()
self.llm_config_tool = LLMConfigurationTool(config=llm_config)
self.llm_config_tool.config.context = system_prompt

# Used in BookFinderLLMOrchestration.generate_response()
answer = self.llm_config_tool.run(
    query=user_query,
    next_trace=next_trace,
    trace=trace
)
```

### SemanticSimilarityTool (ACT-10, ACT-12)

```python
# Initialized in BookFinderAgent.setup()
self.semantic_similarity_tool = SemanticSimilarityTool(config=...)

# Used in BookFinderAgent._get_embedding()
embedding = self.semantic_similarity_tool.run(
    text=user_query,
    docs=None,  # Disable similarity check
    next_trace=next_trace,
    trace=trace
)
```

### CitationTool (ACT-11)

```python
# Initialized in BookFinderAgent.setup()
self.citation_tool = CitationTool(config=citation_config)

# Used in CitationVerificationEngine._verify_single_citation()
highlight, confidence, found = self.citation_tool.clone_for_thread().run(
    citation_key=isbn,
    complete_content=chunk_text,
    cited_text=highlighted_text,
    next_trace=next_trace,
    trace=trace
)
```

## Data Flow Transformations

### 1. Input Request
```json
{
  "user_query": "fantasy books with magic",
  "session_id": "user-123",
  "filters": {"genre_details": "fantasy"}
}
```

### 2. After Validation (ACT-3)
```python
BookFinderRequestSchema(
    user_query="fantasy books with magic",
    session_id="user-123",
    filters=FilterTypeSchema(genre_details="fantasy", ...)
)
```

### 3. After Retrieval (ACT-10, ACT-12)
```python
[
    {
        "isbn": "978-0-123-45678-9",
        "title": "Example Book",
        "context_score": 0.92,  # From scoring engine
        "chunks": [{"text": "...", "similarity": 0.88}]
    },
    # ... more books
]
```

### 4. After Normalization (ACT-13)
```python
[
    {
        "isbn": "978-0-123-45678-9",
        "title": "Example Book",
        "author": "Author Name",
        "context_score": 92.0,
        "publication_year": 2020,
        # ... formatted fields
    }
]
```

### 5. Final Response (ACT-11)
```python
(
    response_text="Here are fantasy books with magic systems...",
    retrieved_documents=[
        {"isbn": "...", "title": "..."}
    ],
    citations=[
        {"title": "...", "url": "...", "description": "..."}
    ],
    bypass_orchestrator_response=False
)
```

## Testing Integration

### Unit Tests by Module

```bash
# Config validation
pytest tests/unit/test_config.py

# Request schemas
pytest tests/unit/test_book_finder_helpers.py

# Agent initialization
pytest tests/unit/test_book_finder_agent.py::test_setup

# Scoring engine
pytest tests/unit/test_scoring_engine.py

# Data utilities
pytest tests/unit/test_book_data_utils.py
```

### Integration Tests by Flow

```bash
# Flow A: Standard retrieval
pytest tests/integration/test_flow_a_standard.py

# Flow B: Pagination
pytest tests/integration/test_flow_b_pagination.py

# Flow C: Filtering
pytest tests/integration/test_flow_c_filtering.py

# End-to-end (all flows)
pytest tests/integration/test_e2e_complete_flow.py
```

## Verification Checklist

- [ ] Config.py loads all environment variables correctly
- [ ] RecommendationAgentBase.setup() initializes tools without errors
- [ ] book_finder_helpers.py validates requests against schema
- [ ] book_finder_database_retrieval.py executes SQL queries correctly
- [ ] book_finder_scoring_engine.py produces weighted scores
- [ ] book_finder_llm_orchestration.py generates valid LLM prompts
- [ ] book_finder_citation_verification.py verifies citations in parallel
- [ ] book_finder_response_assembly.py returns valid 4-tuple
- [ ] book_data_utils.py normalizes data without data loss
- [ ] All three flows (A, B, C) converge at response assembly
- [ ] Citation verification retries once on failure
- [ ] Session state persists across pagination requests
- [ ] Scoring weights sum to 1.0 (with float tolerance)
- [ ] Error handling in RecommendationAgentBase catches all exceptions
- [ ] Fallback response is returned on any agent failure

## Version Compatibility

- Python: 3.9+
- llm-studio-agents: >=1.0.0
- llm-studio-tools: >=1.0.0
- llm-studio-integrations: >=1.0.0
- psycopg2: 2.9.9+
- pydantic: 2.5.0+
- Flask: 3.0.0+

## Future Extensions

The modular design supports extensions:

1. **Custom Scoring**: Modify ScoringEngine.calculate_custom_score()
2. **New Filters**: Add to FilterTypeSchema and FILTER_TABLE_MAPPING
3. **Alternative LLM**: Replace LLMConfigurationTool initialization
4. **Custom Citations**: Extend CitationVerificationEngine
5. **Alternative Embeddings**: Replace SemanticSimilarityTool

## Support

For module-specific issues, refer to:
- ACT-X summary in this codebase for detailed change history
- DEVELOPER_GUIDE.md for operational guidance
- Code comments in individual modules for implementation details

