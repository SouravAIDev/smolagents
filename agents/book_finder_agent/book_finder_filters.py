from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class BookFilterType(str, Enum):
    """
    Enumeration of supported filter types for Book Finder Agent.
    Each filter type corresponds to a specific book domain aspect.
    """
    BOOK_TITLE = "book_title"
    BOOK_SUMMARY = "book_summary"
    GENRE = "genre"
    AUTHOR = "author"
    PUBLICATION_DATE = "publication_date"
    ISBN = "isbn"
    PUBLISHER = "publisher"
    AUDIENCE = "audience"
    SUPPORTING_CHUNKS = "supporting_chunks"


class FilterDetails(BaseModel):
    """
    Pydantic model defining metadata for a single filter type.
    Used by query builders and orchestration logic to construct
    parameterized SQL queries against book tables.
    """
    table: str = Field(
        ...,
        description="Database table name for this filter type"
    )
    search_column: str = Field(
        ...,
        description="Column name for embedding-based or text search"
    )
    return_column: str = Field(
        ...,
        description="Primary key column to retrieve from table"
    )
    filter_title: str = Field(
        ...,
        description="Human-readable label for UI display"
    )
    select_columns: List[str] = Field(
        default_factory=list,
        description="List of columns to SELECT from this table"
    )
    filter_mode: str = Field(
        default="soft_filter",
        description="Filter mode: 'soft_filter' (similarity-based) or 'hard_filter' (exact match)"
    )
    similarity_threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity for soft filters (0.0-1.0)"
    )
    filter_similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Secondary similarity threshold for aggregation (0.0-1.0)"
    )

    class Config:
        extra = "forbid"


class JoinDefinition(BaseModel):
    """
    Defines a join relationship for many-to-many metadata aggregation.
    Used to construct SQL JOINs and STRING_AGG operations.
    """
    from_table: str = Field(
        ...,
        description="Source table name"
    )
    to_table: str = Field(
        ...,
        description="Target table to join with"
    )
    join_column: str = Field(
        ...,
        description="Common column for join predicate"
    )
    aggregation_function: str = Field(
        default="STRING_AGG(column, ', ')",
        description="SQL aggregation function for collapsing multiple rows"
    )
    aggregate_column: str = Field(
        ...,
        description="Column name to aggregate (e.g., 'author_name')"
    )
    result_column: str = Field(
        ...,
        description="Output column alias for aggregated results"
    )

    class Config:
        extra = "forbid"


# Module-level dictionary mapping filter types to their database metadata
FILTER_TABLE_MAPPING: dict = {
    BookFilterType.BOOK_TITLE: FilterDetails(
        table="books",
        search_column="title_embedding",
        return_column="book_id",
        filter_title="Book Title",
        select_columns=["book_id", "title", "author_id", "isbn", "publication_date"],
        filter_mode="soft_filter",
        similarity_threshold=0.65,
        filter_similarity_threshold=0.50
    ),
    BookFilterType.BOOK_SUMMARY: FilterDetails(
        table="book_summaries",
        search_column="summary_embedding",
        return_column="book_id",
        filter_title="Book Summary",
        select_columns=["book_id", "summary_text", "summary_length"],
        filter_mode="soft_filter",
        similarity_threshold=0.65,
        filter_similarity_threshold=0.50
    ),
    BookFilterType.GENRE: FilterDetails(
        table="genres",
        search_column="genre_name_embedding",
        return_column="book_id",
        filter_title="Genre",
        select_columns=["book_id", "genre_name", "genre_id"],
        filter_mode="soft_filter",
        similarity_threshold=0.60,
        filter_similarity_threshold=0.45
    ),
    BookFilterType.AUTHOR: FilterDetails(
        table="authors",
        search_column="author_name_embedding",
        return_column="book_id",
        filter_title="Author",
        select_columns=["book_id", "author_name", "author_id", "biography"],
        filter_mode="soft_filter",
        similarity_threshold=0.60,
        filter_similarity_threshold=0.45
    ),
    BookFilterType.PUBLICATION_DATE: FilterDetails(
        table="books",
        search_column="publication_date",
        return_column="book_id",
        filter_title="Publication Date",
        select_columns=["book_id", "publication_date", "publication_year"],
        filter_mode="hard_filter",
        similarity_threshold=1.0,
        filter_similarity_threshold=1.0
    ),
    BookFilterType.ISBN: FilterDetails(
        table="books",
        search_column="isbn",
        return_column="book_id",
        filter_title="ISBN",
        select_columns=["book_id", "isbn", "isbn_13"],
        filter_mode="hard_filter",
        similarity_threshold=1.0,
        filter_similarity_threshold=1.0
    ),
    BookFilterType.PUBLISHER: FilterDetails(
        table="publishers",
        search_column="publisher_name_embedding",
        return_column="book_id",
        filter_title="Publisher",
        select_columns=["book_id", "publisher_name", "publisher_id", "country"],
        filter_mode="soft_filter",
        similarity_threshold=0.60,
        filter_similarity_threshold=0.45
    ),
    BookFilterType.AUDIENCE: FilterDetails(
        table="audience_details",
        search_column="audience_type_embedding",
        return_column="book_id",
        filter_title="Audience",
        select_columns=["book_id", "audience_type", "age_group"],
        filter_mode="hard_filter",
        similarity_threshold=0.70,
        filter_similarity_threshold=0.55
    ),
    BookFilterType.SUPPORTING_CHUNKS: FilterDetails(
        table="manuscript_chunks",
        search_column="chunk_embedding",
        return_column="book_id",
        filter_title="Supporting Excerpts",
        select_columns=["book_id", "chunk_id", "chunk_text", "page_number"],
        filter_mode="soft_filter",
        similarity_threshold=0.65,
        filter_similarity_threshold=0.50
    )
}


# Dictionary defining complex join relationships for many-to-many metadata aggregation
NORMALIZED_TABLE_MAPPING: dict = {
    "book_to_authors": JoinDefinition(
        from_table="books",
        to_table="authors",
        join_column="book_id",
        aggregation_function="STRING_AGG(a.author_name, ', ' ORDER BY a.author_name)",
        aggregate_column="author_name",
        result_column="all_authors"
    ),
    "book_to_genres": JoinDefinition(
        from_table="books",
        to_table="genres",
        join_column="book_id",
        aggregation_function="STRING_AGG(g.genre_name, ', ' ORDER BY g.genre_name)",
        aggregate_column="genre_name",
        result_column="all_genres"
    ),
    "book_to_contributors": JoinDefinition(
        from_table="books",
        to_table="contributors",
        join_column="book_id",
        aggregation_function="STRING_AGG(c.contributor_name, ', ' ORDER BY c.contributor_name)",
        aggregate_column="contributor_name",
        result_column="all_contributors"
    ),
    "book_to_awards": JoinDefinition(
        from_table="books",
        to_table="prizes",
        join_column="book_id",
        aggregation_function="STRING_AGG(p.prize_name, ', ' ORDER BY p.prize_year DESC)",
        aggregate_column="prize_name",
        result_column="all_prizes"
    ),
    "book_to_locations": JoinDefinition(
        from_table="books",
        to_table="locations",
        join_column="book_id",
        aggregation_function="STRING_AGG(l.location_name, ', ' ORDER BY l.location_name)",
        aggregate_column="location_name",
        result_column="all_locations"
    )
}


def get_filter_details(filter_type: BookFilterType) -> FilterDetails:
    """
    Retrieve FilterDetails for a given BookFilterType.
    
    Args:
        filter_type: The BookFilterType enum value
        
    Returns:
        FilterDetails: Configuration for the specified filter type
        
    Raises:
        KeyError: If filter_type is not found in FILTER_TABLE_MAPPING
    """
    if filter_type not in FILTER_TABLE_MAPPING:
        raise KeyError(f"Filter type {filter_type} not found in FILTER_TABLE_MAPPING")
    return FILTER_TABLE_MAPPING[filter_type]


def get_join_definition(join_key: str) -> JoinDefinition:
    """
    Retrieve JoinDefinition for a given join relationship.
    
    Args:
        join_key: The key identifying the join relationship (e.g., 'book_to_authors')
        
    Returns:
        JoinDefinition: Configuration for the specified join
        
    Raises:
        KeyError: If join_key is not found in NORMALIZED_TABLE_MAPPING
    """
    if join_key not in NORMALIZED_TABLE_MAPPING:
        raise KeyError(f"Join key {join_key} not found in NORMALIZED_TABLE_MAPPING")
    return NORMALIZED_TABLE_MAPPING[join_key]


def validate_filter_table_mapping() -> bool:
    """
    Validates that FILTER_TABLE_MAPPING is correctly configured.
    Checks that all BookFilterType members have corresponding entries
    with valid field values.
    
    Returns:
        bool: True if validation passes, False otherwise
    """
    # Verify all enum members have entries
    for filter_type in BookFilterType:
        if filter_type not in FILTER_TABLE_MAPPING:
            print(f"ERROR: BookFilterType.{filter_type.name} missing from FILTER_TABLE_MAPPING")
            return False
        
        details = FILTER_TABLE_MAPPING[filter_type]
        
        # Verify required fields exist
        if not details.table:
            print(f"ERROR: {filter_type} missing 'table' field")
            return False
        if not details.search_column:
            print(f"ERROR: {filter_type} missing 'search_column' field")
            return False
        if not details.return_column:
            print(f"ERROR: {filter_type} missing 'return_column' field")
            return False
        if not details.filter_title:
            print(f"ERROR: {filter_type} missing 'filter_title' field")
            return False
        
        # Verify similarity thresholds are valid floats
        if not (0.0 <= details.similarity_threshold <= 1.0):
            print(f"ERROR: {filter_type} similarity_threshold out of range [0.0, 1.0]")
            return False
        if not (0.0 <= details.filter_similarity_threshold <= 1.0):
            print(f"ERROR: {filter_type} filter_similarity_threshold out of range [0.0, 1.0]")
            return False
    
    return True


def validate_normalized_table_mapping() -> bool:
    """
    Validates that NORMALIZED_TABLE_MAPPING is correctly configured.
    Checks that all join definitions have valid field values.
    
    Returns:
        bool: True if validation passes, False otherwise
    """
    for join_key, join_def in NORMALIZED_TABLE_MAPPING.items():
        if not join_def.from_table:
            print(f"ERROR: {join_key} missing 'from_table' field")
            return False
        if not join_def.to_table:
            print(f"ERROR: {join_key} missing 'to_table' field")
            return False
        if not join_def.join_column:
            print(f"ERROR: {join_key} missing 'join_column' field")
            return False
        if not join_def.aggregate_column:
            print(f"ERROR: {join_key} missing 'aggregate_column' field")
            return False
        if not join_def.result_column:
            print(f"ERROR: {join_key} missing 'result_column' field")
            return False
    
    return True

