from enum import Enum
from typing import Optional, Dict, List, Any, Literal, Tuple
from pydantic import BaseModel, Field, ValidationError
import logging

logger = logging.getLogger(__name__)


class BookFinderFilterType(str, Enum):
    """
    Enumeration of all supported book domain filters for semantic and exact-match search.
    Maps to specific book_*_backup_2 tables in the database.
    """
    BOOK_SUMMARY_DETAILS = "book_summary_details"
    GENRE_DETAILS = "genre_details"
    SEARCH_SENTENCE = "search_sentence"
    SUPPORTING_EXCERPTS = "supporting_excerpts"
    CONTRIBUTOR_DETAILS = "contributor_details"
    CONTRIBUTOR_BIOGRAPHY_DETAILS = "contributor_biography_details"
    CHARACTER_DETAILS = "character_details"
    QUOTE_DETAILS = "quote_details"
    AUDIENCE_DETAILS = "audience_details"
    LOCATION_DETAILS = "location_details"
    SECTION_DETAILS = "section_details"
    PUBLISHER_DETAILS = "publisher_details"
    IMPRINT_DETAILS = "imprint_details"
    PRIZE_DETAILS = "prize_details"


class FilterTypeSchema(BaseModel):
    """
    Pydantic schema for request filters. All fields are optional.
    Only non-None filters will be active during retrieval.
    Supports both semantic (string-based) and structured (dict/enum) filters.
    """

    book_summary_details: Optional[str] = Field(
        None,
        description="Filter by book summary content. Supports semantic search over book summaries."
    )
    genre_details: Optional[str] = Field(
        None,
        description="Filter by genre. Examples: Fiction, Mystery, Science Fiction, Romance."
    )
    search_sentence: Optional[str] = Field(
        None,
        description="Search for specific sentences or excerpts within book content."
    )
    supporting_excerpts: Optional[str] = Field(
        None,
        description="Filter by supporting manuscript excerpts and context."
    )
    contributor_details: Optional[str] = Field(
        None,
        description="Filter by contributor information (author name, role, etc.)."
    )
    contributor_biography_details: Optional[str] = Field(
        None,
        description="Filter by contributor biography and background information."
    )
    character_details: Optional[str] = Field(
        None,
        description="Filter by character names and descriptions within books."
    )
    quote_details: Optional[str] = Field(
        None,
        description="Filter by notable quotes from books."
    )
    audience_details: Optional[str] = Field(
        None,
        description="Filter by target audience information (age group, demographics)."
    )
    location_details: Optional[str] = Field(
        None,
        description="Filter by geographic locations mentioned in books."
    )
    section_details: Optional[str] = Field(
        None,
        description="Filter by book sections, chapters, or parts."
    )
    publisher_details: Optional[str] = Field(
        None,
        description="Filter by publisher information and details."
    )
    imprint_details: Optional[str] = Field(
        None,
        description="Filter by publishing imprint information."
    )
    prize_details: Optional[str] = Field(
        None,
        description="Filter by awards and prizes received by books."
    )

    class Config:
        extra = "ignore"

    def get_active_filters(self) -> Dict[str, Any]:
        """
        Return only non-None filter parameters.
        Used to determine which database tables need to be queried.
        """
        return {k: v for k, v in self.model_dump().items() if v is not None}


class BookFinderRequestSchema(BaseModel):
    """
    Pydantic schema for validating incoming Book Finder Agent requests.
    Enforces mandatory fields and normalizes optional parameters.
    """

    user_query: str = Field(
        ...,
        min_length=1,
        description="The user's natural-language question about books."
    )
    session_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the user's session. Used for pagination and state management."
    )
    show_more_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional pagination object. Present when user requests 'Show More' results from a previous query."
    )
    filters: Optional[FilterTypeSchema] = Field(
        None,
        description="Optional filters to narrow search scope. Defaults to empty if absent."
    )

    class Config:
        extra = "ignore"

    def get_filters_dict(self) -> Dict[str, Any]:
        """
        Extract active filters as a dictionary.
        Returns empty dict if no filters are specified.
        """
        if self.filters is None:
            return {}
        return self.filters.get_active_filters()

    def is_pagination_request(self) -> bool:
        """
        Determine if this request is a pagination ('Show More') request.
        True if show_more_details is present and non-empty.
        """
        return self.show_more_details is not None and len(self.show_more_details) > 0


class NormalizedTableMapping(BaseModel):
    """
    Schema for normalized table join configuration.
    Used by filters that require multi-table joins for deduplication.
    """
    normalized_table: str = Field(
        ...,
        description="Name of the normalized table (e.g., book_contributor_normalized_backup_2)."
    )
    normalized_primary_key: str = Field(
        ...,
        description="Primary key in normalized table (e.g., 'normalized_contributor_id')."
    )
    source_foreign_key: str = Field(
        ...,
        description="Foreign key in source table linking to normalized table (e.g., 'contributor_id')."
    )
    normalized_foreign_key: str = Field(
        ...,
        description="Foreign key in normalized table (e.g., 'contributor_id')."
    )
    book_id_column: str = Field(
        ...,
        description="Column in normalized table containing the book ISBN."
    )
    select_columns: List[str] = Field(
        default_factory=list,
        description="Mandatory columns to retrieve from normalized table."
    )


class FilterDetails(BaseModel):
    """
    Schema for filter configuration and metadata.
    Captures all information needed to execute a filter's database query,
    including table name, search column, similarity thresholds, and vector/keyword weights.
    """
    table: str = Field(
        ...,
        description="Name of the backup table to query (e.g., book_summary_backup_2)."
    )
    search_column: str = Field(
        ...,
        description="Column name for embedding vector or text search (e.g., summary_embeddings or title)."
    )
    return_column: str = Field(
        ...,
        description="Column to return as the unique identifier (e.g., isbn)."
    )
    filter_title: str = Field(
        ...,
        description="Human-readable name for this filter."
    )
    select_columns: List[str] = Field(
        default_factory=list,
        description="List of columns to retrieve from the table."
    )
    primary_key: str = Field(
        ...,
        description="Primary key column in the source table."
    )
    mapping_type: str = Field(
        default="single",
        description="Type of join mapping: 'single' for 1:1 joins, 'multiple' for 1:N joins."
    )
    filter_location: Optional[str] = Field(
        None,
        description="Metadata about where this filter's data originates (e.g., 'book_data')."
    )
    filter_mode: str = Field(
        default="soft_filter",
        description="Type of filter: 'soft_filter' for semantic search, 'hard_filter' for exact match."
    )
    select_exclude_columns: Optional[List[str]] = Field(
        None,
        description="Columns to explicitly exclude from retrieval."
    )
    search_type: Optional[str] = Field(
        None,
        description="Type of search: 'semantic_search', 'exact_match', or 'keyword_search'."
    )
    fuzzy_features: Optional[List[str]] = Field(
        None,
        description="Columns for fuzzy/text search matching (used for keyword scoring)."
    )
    vector_weight: Optional[float] = Field(
        default=1.0,
        description="Weight for semantic similarity in combined scoring (0.0 to 1.0)."
    )
    fuzzy_weight: Optional[float] = Field(
        default=0.0,
        description="Weight for keyword/fuzzy matching in combined scoring (0.0 to 1.0)."
    )
    normalized_mapping: Optional[NormalizedTableMapping] = Field(
        None,
        description="Optional configuration for multi-table joins via a normalized table."
    )
    similarity_threshold: Optional[float] = Field(
        default=0.65,
        description="Minimum cosine similarity for semantic search results (soft filter threshold)."
    )
    filter_similarity_threshold: Optional[float] = Field(
        default=0.65,
        description="Minimum cosine similarity for hard filters and specific attributes."
    )


# Global registry mapping all book domain filters to their database configurations
FILTER_TABLE_MAPPING: Dict[BookFinderFilterType, FilterDetails] = {
    BookFinderFilterType.BOOK_SUMMARY_DETAILS: FilterDetails(
        table="book_summary_backup_2",
        search_column="summary_embeddings",
        return_column="isbn",
        filter_title="Book Summary",
        select_columns=["isbn", "book_title", "book_summary"],
        primary_key="isbn",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["book_title", "book_summary"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.GENRE_DETAILS: FilterDetails(
        table="book_metadata_backup_2",
        search_column="genre_embeddings",
        return_column="isbn",
        filter_title="Genre",
        select_columns=["isbn", "book_title", "genre"],
        primary_key="isbn",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["genre"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.SEARCH_SENTENCE: FilterDetails(
        table="book_content_chunked_backup_2",
        search_column="chunk_embeddings",
        return_column="isbn",
        filter_title="Content Chunks",
        select_columns=["isbn", "chunk_id", "chunk_text"],
        primary_key="chunk_id",
        mapping_type="multiple",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["chunk_text"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.SUPPORTING_EXCERPTS: FilterDetails(
        table="book_content_chunked_backup_2",
        search_column="chunk_embeddings",
        return_column="isbn",
        filter_title="Supporting Excerpts",
        select_columns=["isbn", "chunk_id", "chunk_text"],
        primary_key="chunk_id",
        mapping_type="multiple",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["chunk_text"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.CONTRIBUTOR_DETAILS: FilterDetails(
        table="book_contributors_backup_2",
        search_column="contributor_name_embeddings",
        return_column="isbn",
        filter_title="Contributors",
        select_columns=["isbn", "contributor_id", "contributor_name", "contributor_role"],
        primary_key="contributor_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["contributor_name", "contributor_role"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.CONTRIBUTOR_BIOGRAPHY_DETAILS: FilterDetails(
        table="book_contributors_backup_2",
        search_column="biography_embeddings",
        return_column="isbn",
        filter_title="Contributor Biography",
        select_columns=["isbn", "contributor_id", "contributor_name", "biography"],
        primary_key="contributor_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["biography"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.CHARACTER_DETAILS: FilterDetails(
        table="book_notable_characters_backup_2",
        search_column="character_embeddings",
        return_column="isbn",
        filter_title="Characters",
        select_columns=["isbn", "character_id", "character_name", "character_description"],
        primary_key="character_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["character_name", "character_description"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.QUOTE_DETAILS: FilterDetails(
        table="book_notable_quotes_backup_2",
        search_column="quote_embeddings",
        return_column="isbn",
        filter_title="Notable Quotes",
        select_columns=["isbn", "quote_id", "quote_text"],
        primary_key="quote_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["quote_text"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.AUDIENCE_DETAILS: FilterDetails(
        table="book_audience_backup_2",
        search_column="audience_embeddings",
        return_column="isbn",
        filter_title="Audience",
        select_columns=["isbn", "audience_id", "audience_type", "audience_description"],
        primary_key="audience_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["audience_type", "audience_description"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.LOCATION_DETAILS: FilterDetails(
        table="geo_location_backup_2",
        search_column="location_embeddings",
        return_column="isbn",
        filter_title="Locations",
        select_columns=["isbn", "location_id", "location_name", "location_type"],
        primary_key="location_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["location_name"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.SECTION_DETAILS: FilterDetails(
        table="book_content_sections_backup_2",
        search_column="section_embeddings",
        return_column="isbn",
        filter_title="Sections",
        select_columns=["isbn", "section_id", "section_title", "section_content"],
        primary_key="section_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["section_title"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.PUBLISHER_DETAILS: FilterDetails(
        table="book_publishers_backup_2",
        search_column="publisher_name_embeddings",
        return_column="isbn",
        filter_title="Publisher",
        select_columns=["isbn", "publisher_id", "publisher_name", "publisher_location"],
        primary_key="publisher_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["publisher_name"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.IMPRINT_DETAILS: FilterDetails(
        table="book_imprint_details_backup_2",
        search_column="imprint_name_embeddings",
        return_column="isbn",
        filter_title="Imprint",
        select_columns=["isbn", "imprint_id", "imprint_name"],
        primary_key="imprint_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["imprint_name"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
    BookFinderFilterType.PRIZE_DETAILS: FilterDetails(
        table="book_prize_details_backup_2",
        search_column="prize_embeddings",
        return_column="isbn",
        filter_title="Prizes and Awards",
        select_columns=["isbn", "prize_id", "prize_name", "prize_year"],
        primary_key="prize_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        fuzzy_features=["prize_name"],
        vector_weight=1.0,
        fuzzy_weight=0.0,
        similarity_threshold=0.65,
        filter_similarity_threshold=0.65
    ),
}


FILTER_TYPE_TO_TEXT_MAP = {
    BookFinderFilterType.BOOK_SUMMARY_DETAILS: "Book Summary",
    BookFinderFilterType.GENRE_DETAILS: "Genre Details",
    BookFinderFilterType.SEARCH_SENTENCE: "Search Sentence",
    BookFinderFilterType.SUPPORTING_EXCERPTS: "Supporting Excerpts",
    BookFinderFilterType.CONTRIBUTOR_DETAILS: "Contributor Details",
    BookFinderFilterType.CONTRIBUTOR_BIOGRAPHY_DETAILS: "Contributor Biography",
    BookFinderFilterType.CHARACTER_DETAILS: "Character Details",
    BookFinderFilterType.QUOTE_DETAILS: "Notable Quotes",
    BookFinderFilterType.AUDIENCE_DETAILS: "Audience Details",
    BookFinderFilterType.LOCATION_DETAILS: "Location Details",
    BookFinderFilterType.SECTION_DETAILS: "Section Details",
    BookFinderFilterType.PUBLISHER_DETAILS: "Publisher Details",
    BookFinderFilterType.IMPRINT_DETAILS: "Imprint Details",
    BookFinderFilterType.PRIZE_DETAILS: "Prize Details",
}


def validate_request(payload: dict) -> BookFinderRequestSchema:
    """
    Validate and normalize incoming request payload.
    
    Enforces:
    - Required fields: user_query, session_id
    - Optional fields: show_more_details, filters
    - All strings are trimmed and validated as non-empty
    - Filters are validated against FilterTypeSchema
    
    Args:
        payload (dict): Raw HTTP request payload
    
    Returns:
        BookFinderRequestSchema: Validated, normalized request object
    
    Raises:
        ValidationError: If required fields are missing or invalid
    """
    try:
        # Pydantic will handle validation and type coercion
        request_schema = BookFinderRequestSchema(**payload)
        logger.info(f"Request validated successfully. Session: {request_schema.session_id}, IsShowMore: {request_schema.is_pagination_request()}")
        return request_schema
    except ValidationError as e:
        logger.error(f"Request validation failed: {e.json()}")
        raise e


def get_filter_details(filter_type: BookFinderFilterType) -> Optional[FilterDetails]:
    """
    Retrieve the filter configuration for a specific filter type.
    
    Args:
        filter_type (BookFinderFilterType): The filter type enum
    
    Returns:
        FilterDetails: Configuration for the filter, or None if not found
    """
    return FILTER_TABLE_MAPPING.get(filter_type, None)


def handle_filtered_context(
    session_id: str,
    filters: Dict[str, Any],
    sql_executor_tool: Any,
    context_table: str,
    next_trace: Optional[Dict] = None,
    trace: Optional[Dict] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Retrieve filtered records from session context table using JSONB metadata filtering.
    
    This implements Step C1 (Filtered Context Retrieval) by querying the session context
    table for records matching the supplied filters. Uses PostgreSQL JSONB @> operator
    for exact-match metadata filtering.
    
    Args:
        session_id (str): Session identifier for scoping the query
        filters (Dict[str, Any]): Filter criteria as dictionary (e.g., {"genre": "Fiction"})
        sql_executor_tool (Any): SQLExecutorTool instance for database queries
        context_table (str): Name of the session context table
        next_trace (Optional[Dict]): Trace handler for nested calls
        trace (Optional[Dict]): Trace handler for observability
    
    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, str]]: 
            - List of filtered book records from session context
            - Mapping of ISBN -> database record ID for downstream operations
    
    Raises:
        DatabaseConnectionError: If query execution fails
    
    Example:
        >>> filters = {"genre": "Mystery", "audience": "Adult"}
        >>> records, isbn_map = handle_filtered_context(
        ...     session_id="sess_123",
        ...     filters=filters,
        ...     sql_executor_tool=tool,
        ...     context_table="retrieved_document_details"
        ... )
    """
    import json
    
    try:
        # Validate inputs
        if not session_id or not filters:
            logger.warning(f"Invalid input: session_id={session_id}, filters={filters}")
            return [], {}
        
        logger.info(f"Applying JSONB filters to session context. Session: {session_id}, Filters: {filters}")
        
        # Build JSONB filter conditions dynamically
        filter_conditions = []
        filter_params = [session_id]
        
        # Convert filters to JSONB containment check
        # Each filter key-value pair is checked against the metadata JSONB column
        for filter_key, filter_value in filters.items():
            # PostgreSQL JSONB @> operator checks if left operand contains right operand
            # We construct a JSON object to match against the metadata column
            filter_json = {filter_key: filter_value}
            filter_conditions.append(f"metadata @> %s")
            filter_params.append(json.dumps(filter_json))
        
        # Construct WHERE clause
        where_clause = f"session_id = %s"
        if filter_conditions:
            where_clause += " AND (" + " OR ".join(filter_conditions) + ")"
        
        # Build the final query
        query = f"""
        SELECT 
            id, 
            session_id, 
            question, 
            isbn, 
            metadata,
            context_score,
            is_displayed,
            is_expired,
            display_count,
            created_at,
            updated_at
        FROM {context_table}
        WHERE {where_clause}
        AND is_expired = FALSE
        ORDER BY context_score DESC
        """
        
        logger.debug(f"Executing filtered context query with {len(filter_params)} parameters")
        
        # Execute the query
        rows = sql_executor_tool.run(
            sql_query=query,
            params=tuple(filter_params),
            next_trace=next_trace,
            trace=trace,
        )
        
        if not rows:
            logger.info(f"No documents matched filters for session {session_id}")
            return [], {}
        
        logger.info(f"Retrieved {len(rows)} documents matching filters")
        
        # Parse metadata and build output
        filtered_records = []
        isbn_to_id_map = {}
        
        for row in rows:
            try:
                # Parse metadata JSONB field
                metadata = row.get('metadata')
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                elif not isinstance(metadata, dict):
                    metadata = {}
                
                # Normalize ISBN
                isbn = row.get('isbn', '')
                record_id = row.get('id')
                
                # Build record dictionary
                record = {
                    'id': record_id,
                    'isbn': isbn,
                    'session_id': row.get('session_id'),
                    'question': row.get('question'),
                    'metadata': metadata,
                    'context_score': row.get('context_score', 0.0),
                    'is_displayed': row.get('is_displayed', False),
                    'display_count': row.get('display_count', 0),
                }
                
                filtered_records.append(record)
                
                # Build ISBN to ID mapping for downstream operations
                if isbn and record_id:
                    isbn_to_id_map[isbn] = str(record_id)
                
            except Exception as e:
                logger.warning(f"Skipping malformed record: {e}")
                continue
        
        logger.info(
            f"Processed {len(filtered_records)} valid records, "
            f"ISBN mapping size: {len(isbn_to_id_map)}"
        )
        
        return filtered_records, isbn_to_id_map
        
    except Exception as e:
        logger.error(f"Error in handle_filtered_context: {e}", exc_info=True)
        raise Exception(f"DatabaseConnectionError: Failed to retrieve filtered context: {str(e)}") from e

