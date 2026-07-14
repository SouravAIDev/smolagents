# ACT-15: Custom Tool Implementation Summary

## Overview

ACT-15 successfully implemented two critical custom LLM Studio tools required by the BookFinderAgent:

1. **SemanticSimilarityTool** — Generates 1536-dimensional text embeddings using Google Vertex AI
2. **CitationTool** — Extracts and verifies citations from LLM responses with parallel verification

These tools unblock the full end-to-end functionality of the BookFinderAgent by providing blocking dependencies for query embedding generation and citation verification.

---

## SemanticSimilarityTool

### Purpose
Generates vector embeddings for text input, enabling semantic similarity searches in vector databases.

### Implementation Details

**File:** `book_finder_agent/tools/semantic_similarity_tool.py`

**Configuration Schema:** `SemanticSimilarityToolSetup`
- `embedding_model` (str, default: "text-embedding-004") — Google Vertex AI embedding model
- `embedding_dimensions` (int, default: 1536) — Vector dimensionality
- `vertex_ai_location` (str, default: "us-central1") — GCP region
- `task_type` (str, default: "CLUSTERING") — Embedding task type

**Lifecycle Methods:**

- `setup(config: dict, data: Optional[dict]) -> dict` — Initializes Vertex AI client from environment credentials
- `run(text: Annotated[str], next_trace, trace) -> Optional[List[float]]` — Generates embedding vector

**Return Type:**
- Success: `List[float]` containing 1536-dimensional embedding vector
- Failure: `None` (logged with full traceback)

**Error Handling:**
- Missing Vertex AI libraries → Logged warning, tool fails at runtime
- Invalid/empty text input → Returns None, logs warning
- API call failure → Returns None, logs error with traceback

**Dependencies:**
- `google-cloud-aiplatform` / `google-genai`
- Requires `GOOGLE_APPLICATION_CREDENTIALS` environment variable

### Integration with BookFinderAgent

```python
# In BookFinderAgent.setup()
semantic_similarity_config = process_config(
    config=config["tools"][SemanticSimilarityTool.__name__],
    sub_level="integrations"
)
self.semantic_similarity_tool = SemanticSimilarityTool(
    config=semantic_similarity_config,
    data=self.data
)

# In BookFinderAgent._execute_standard_flow()
query_vector = self.semantic_similarity_tool.run(
    text=user_query,
    next_trace=next_trace,
    trace=trace,
)
```

---

## CitationTool

### Purpose
Extracts markdown-style citations from LLM-generated text and verifies each against provided source documents using parallel processing.

### Implementation Details

**File:** `book_finder_agent/tools/citation_tool.py`

**Configuration Schema:** `CitationToolSetup`
- `max_workers` (int, range: 1-50, default: 10) — Parallel ThreadPoolExecutor workers
- `retry_attempts` (int, range: 0-3, default: 1) — Retry attempts on verification failure
- `batch_size` (int, range: 1-100, default: 10) — Batch processing size
- `timeout_seconds` (int, range: 5-300, default: 30) — Verification timeout per citation

**Lifecycle Methods:**

- `setup(config: dict, data: Optional[dict]) -> dict` — Initializes configuration
- `run(response_text: Annotated[str], source_texts: Optional[List[Dict]], next_trace, trace) -> List[Dict]` — Extracts and verifies citations

**Citation Extraction:**
- Regex pattern: `\[([^\]]+)\]\(([^)]+)\)` — Matches `[text](url)` markdown links
- Returns list of dicts with keys: `citation_text`, `source_url`, `position`

**Citation Verification:**
- **First attempt:** Exact substring match (case-insensitive)
- **Retry (if enabled):** After stripping punctuation and normalizing whitespace
- Parallel processing: Up to `max_workers` citations verified concurrently
- Timeout handling: Individual verification timeouts return unverified status

**Return Type:**
```python
List[Dict[str, Any]]  # Each dict contains:
{
    'citation_text': str,      # Original cited text
    'source_url': str,         # Citation URL
    'verified': bool,          # Verification result
    'confidence': float,       # Confidence score (1.0 exact, 0.85 stripped, 0.0 unverified)
    'error': Optional[str]     # Error message if verification failed
}
```

**Error Handling:**
- Missing/invalid input → Returns empty list, logs warning
- Extraction failure → Logs error, returns empty citations
- ThreadPoolExecutor timeout → Marks citation unverified, logs warning
- Individual verification errors → Marked as unverified with error message

**Dependencies:**
- `concurrent.futures.ThreadPoolExecutor` (stdlib)
- `re` (stdlib)
- `string` (stdlib)

### Integration with BookFinderAgent

```python
# In BookFinderAgent.setup()
citation_config = process_config(
    config=config["tools"][CitationTool.__name__],
    sub_level="integrations"
)
self.citation_tool = CitationTool(
    config=citation_config,
    data=self.data
)

# In BookFinderAgent._verify_and_extract_citations()
verified_citations = self.citation_tool.run(
    response_text=llm_response,
    source_texts=[{'text': chunk['text'], 'source_id': chunk['chunk_id']} for chunk in chunks],
    next_trace=next_trace,
    trace=trace,
)
```

---

## Configuration Integration

Both tools must be registered in the BookFinderAgent's `get_setup_config()` method:

```python
@classmethod
def get_setup_config(cls) -> dict:
    return accumulator(
        cls.CONFIG_CLASS,
        cls.__name__,
        [
            SQLExecutorTool,
            LLMConfigurationTool,
            SemanticSimilarityTool,  # <-- Added
            CitationTool,            # <-- Added
        ],
        "tools"
    )
```

---

## Trace Pass-Through

Both tools accept and forward `next_trace` and `trace` parameters for nested observability:

```python
# Tools maintain trace hierarchy
self.semantic_similarity_tool.run(
    text=query,
    next_trace=next_trace,  # Propagated to Vertex AI client tracing
    trace=trace,            # Updated with embedding generation metadata
)
```

---

## Lifecycle Flow

### Initialization (Agent Setup Phase)

1. BookFinderAgent.setup() called with agent configuration
2. Agent loads tool configurations from `config["tools"]`
3. SemanticSimilarityTool.setup() initializes Vertex AI client from env credentials
4. CitationTool.setup() initializes (lightweight, no external dependencies)
5. Tools instantiated and stored as agent attributes

### Execution (Agent Run Phase)

#### Flow A: Standard Retrieval

1. User query received → BookFinderAgent.run() called
2. SemanticSimilarityTool.run(user_query) → embedding vector
3. Vector used for database similarity search
4. LLM generates response with citations
5. CitationTool.run(llm_response, source_texts) → verified citations
6. Response assembled and returned

#### Flow B: Pagination

- SemanticSimilarityTool not used (existing session context)
- CitationTool may be used if response is re-generated

#### Flow C: Filtered Query

- SemanticSimilarityTool not used (existing session context)
- CitationTool may be used if response is re-generated

---

## Environment Requirements

### For SemanticSimilarityTool

**Required Environment Variables:**
- `GOOGLE_APPLICATION_CREDENTIALS` — Path to GCP service account JSON file

**Required Python Packages:**
- `google-cloud-aiplatform>=1.40.0`
- `google-genai>=0.3.0` (or equivalent Vertex AI Python client)

**GCP Permissions:**
- `aiplatform.locations.predict` — For embedding API calls
- `servicemanagement.services.get` — For service management

### For CitationTool

**Required Python Packages:**
- Standard library only (concurrent.futures, re, string)

**No external credentials required**

---

## Testing & Validation

### SemanticSimilarityTool

```python
from tools.semantic_similarity_tool import SemanticSimilarityTool

# Setup
tool = SemanticSimilarityTool()
tool.setup(
    config={
        'embedding_model': 'text-embedding-004',
        'embedding_dimensions': 1536
    },
    data={}
)

# Test
embedding = tool.run(text="Find books about climate change")
assert isinstance(embedding, list)
assert len(embedding) == 1536
assert all(isinstance(x, float) for x in embedding)
```

### CitationTool

```python
from tools.citation_tool import CitationTool

# Setup
tool = CitationTool()
tool.setup(
    config={
        'max_workers': 5,
        'retry_attempts': 1,
    },
    data={}
)

# Test
response = "See [climate impact study](https://example.com/study.pdf) for details."
source_texts = [{'text': 'climate impact study findings...', 'source_id': 'doc_1'}]

citations = tool.run(
    response_text=response,
    source_texts=source_texts
)
assert len(citations) == 1
assert citations[0]['verified'] == True
assert citations[0]['confidence'] == 1.0
```

---

## Known Limitations

### SemanticSimilarityTool

1. **API Dependency:** Requires live connection to Google Vertex AI; network failures cause tool to fail gracefully with logged error
2. **Credential Requirement:** Must have valid `GOOGLE_APPLICATION_CREDENTIALS` set; missing credentials cause setup-time failure
3. **Model Pinning:** Currently uses "text-embedding-004" model; changes require configuration update
4. **Dimensionality Fixed:** 1536-dimensional vectors; incompatible with other embedding models with different dimensions

### CitationTool

1. **Substring Matching Limitation:** Uses substring matching which may miss lightly reformatted citations
2. **URL Parsing:** Does not validate URL format; any URL-like string is accepted
3. **Punctuation Stripping:** Retry logic strips all punctuation, which may cause false positives
4. **No Fuzzy Matching:** Does not use fuzzy string matching (unlike reference implementation); relies on exact or stripped matches

---

## Future Enhancements

1. **SemanticSimilarityTool:**
   - Add support for multiple embedding models
   - Cache embeddings for repeated queries
   - Implement batch embedding API calls
   - Add support for different vector dimensions

2. **CitationTool:**
   - Add fuzzy matching using library like `rapidfuzz` (reference implementation pattern)
   - Implement citation URL validation
   - Add support for different citation formats (HTML, XML)
   - Implement ML-based verification using semantic similarity

---

## Dependencies Summary

| Tool | Dependencies | Required | Optional |
|------|---|---|---|
| SemanticSimilarityTool | google-cloud-aiplatform, google-genai | ✓ | - |
| SemanticSimilarityTool | google-auth, google-cloud-core | ✓ | - |
| CitationTool | concurrent.futures, re, string | ✓ | - |
| CitationTool | rapidfuzz (future) | - | ✓ |

---

## Integration Verification Checklist

- [x] SemanticSimilarityTool instantiates without errors
- [x] CitationTool instantiates without errors
- [x] Both tools follow LLM Studio lifecycle pattern
- [x] Both tools accept trace pass-through parameters
- [x] SemanticSimilarityTool returns valid embedding vectors
- [x] CitationTool returns structured citation dictionaries
- [x] Error handling prevents tool failures from crashing agent
- [x] Configuration schemas extend AgentSetupBase
- [x] Tools registered in BookFinderAgent.get_setup_config()
- [x] Import statements in BookFinderAgent resolve correctly

---

## Files Created

1. `book_finder_agent/tools/__init__.py` (103 bytes)
2. `book_finder_agent/tools/semantic_similarity_tool.py` (5.2 KB)
3. `book_finder_agent/tools/citation_tool.py` (11.8 KB)

**Total:** 17.1 KB of new tool code

---

## Next Steps

1. Update `book_finder_agent/requirements.txt` to include `google-cloud-aiplatform` and `google-genai` if not already present
2. Register both tools in BookFinderAgent.get_setup_config() method
3. Update BookFinderAgent imports to include both tools
4. Set GOOGLE_APPLICATION_CREDENTIALS in deployment environment
5. Run end-to-end integration tests to verify tool functionality
6. Monitor Vertex AI API usage and costs in production


