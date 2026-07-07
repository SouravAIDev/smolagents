from enum import Enum
from typing import Optional, Dict, List, Any, Literal
from pydantic import BaseModel, Field


class BookFilterType(str, Enum):
    """Enumeration defining book filter categories for retrieval operations."""
    AUTHOR_DETAILS = "author_details"
    AUTHOR_BIOGRAPHY = "author_biography_details"
    
    BOOK_TITLE = "book_title"
    BOOK_SUMMARY = "book_summary_details"
    BOOK_PUBLICATION_DATE = "book_publication_date_details"
    
    GENRE_DETAILS = "genre_details"
    AUDIENCE_DETAILS = "audience_details"
    
    ISBN_DETAILS = "isbn_details"
    PUBLISHER_DETAILS = "publisher_details"
    IMPRINT_DETAILS = "imprint_details"
    
    PRIZE_DETAILS = "prize_details"
    LOCATION_DETAILS = "location_details"
    SECTION_DETAILS = "section_details"
    CHARACTER_DETAILS = "character_details"
    
    SUPPORTING_EXCERPTS = "supporting_excerpts"
    QUOTES_DETAILS = "quotes_details"


class FilterTypeSchema(BaseModel, extra="ignore"):
    """Pydantic schema for validating and normalizing filter parameters."""
    author_details: Optional[str] = Field(None, description="Filter by author name or biography.")
    author_biography_details: Optional[str] = Field(None, description="Filter by author biography details.")
    
    book_title: Optional[str] = Field(None, description="Filter by book title or keywords in title.")
    book_summary_details: Optional[str] = Field(None, description="Filter by book summary or description.")
    book_publication_date_details: Optional[Dict[str, Any]] = Field(None, description="Filter by publication date. Expected: {'condition': 'after'/'before'/'equal', 'date': 'YYYY-MM-DD'}")
    
    genre_details: Optional[str] = Field(None, description="Filter by book genre or category.")
    audience_details: Optional[str] = Field(None, description="Filter by target audience (e.g., children, adults, young adults).")
    
    isbn_details: Optional[str] = Field(None, description="Filter by ISBN or ISBN-related metadata.")
    publisher_details: Optional[str] = Field(None, description="Filter by publisher name or details.")
    imprint_details: Optional[str] = Field(None, description="Filter by imprint or sub-publisher.")
    
    prize_details: Optional[str] = Field(None, description="Filter by awards or prizes received.")
    location_details: Optional[str] = Field(None, description="Filter by book setting or location.")
    section_details: Optional[str] = Field(None, description="Filter by book section or chapter.")
    character_details: Optional[str] = Field(None, description="Filter by character name or description.")
    
    supporting_excerpts: Optional[str] = Field(None, description="Filter by supporting book excerpts or manuscript text.")
    quotes_details: Optional[str] = Field(None, description="Filter by notable quotes from the book.")
    
    def get_run_params(self) -> Dict[str, Any]:
        """Return only non-None filter parameters."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


FILTER_TYPE_TO_TEXT_MAP = {
    BookFilterType.AUTHOR_DETAILS: "Author Details",
    BookFilterType.AUTHOR_BIOGRAPHY: "Author Biography",
    
    BookFilterType.BOOK_TITLE: "Book Title",
    BookFilterType.BOOK_SUMMARY: "Book Summary",
    BookFilterType.BOOK_PUBLICATION_DATE: "Publication Date",
    
    BookFilterType.GENRE_DETAILS: "Genre",
    BookFilterType.AUDIENCE_DETAILS: "Target Audience",
    
    BookFilterType.ISBN_DETAILS: "ISBN",
    BookFilterType.PUBLISHER_DETAILS: "Publisher",
    BookFilterType.IMPRINT_DETAILS: "Imprint",
    
    BookFilterType.PRIZE_DETAILS: "Awards & Prizes",
    BookFilterType.LOCATION_DETAILS: "Book Setting",
    BookFilterType.SECTION_DETAILS: "Book Section",
    BookFilterType.CHARACTER_DETAILS: "Characters",
    
    BookFilterType.SUPPORTING_EXCERPTS: "Book Excerpts",
    BookFilterType.QUOTES_DETAILS: "Quotes",
}


class NormalizedTableMapping(BaseModel):
    """Schema for normalized table join configuration."""
    normalized_table: str = Field(..., description="Name of the normalized table (e.g., normalized_author_mapping).")
    normalized_primary_key: str = Field(..., description="Primary key in normalized table (e.g., 'normalized_author_id').")
    source_foreign_key: str = Field(..., description="Foreign key in source table linking to normalized table (e.g., 'author_id').")
    normalized_foreign_key: str = Field(..., description="Foreign key in normalized table (e.g., 'author_id').")
    book_id_column: str = Field(..., description="Column in normalized table containing book_id.")
    select_columns: List[str] = Field(default_factory=list, description="Mandatory columns to retrieve from normalized table.")


class FilterDetails(BaseModel):
    """Schema for filter configuration and retrieval metadata."""
    table: str
    search_column: str
    return_column: str
    filter_title: str
    select_columns: List[str]
    primary_key: str
    mapping_type: str
    filter_location: Optional[str] = None
    filter_mode: str
    select_exclude_columns: Optional[List[str]] = None
    search_type: Optional[str] = None
    fuzzy_features: Optional[List[str]] = None  # Columns for fuzzy/text search matching
    vector_weight: Optional[float] = 1  # Weight for vector similarity (default 100%)
    fuzzy_weight: Optional[float] = 0  # Weight for fuzzy matching (default 0%)
    normalized_mapping: Optional[NormalizedTableMapping] = Field(None, description="Optional normalized table mapping for multi-level joins.")
    similarity_threshold: Optional[float] = None
    filter_similarity_threshold: Optional[float] = None


BOOK_FILTER_MAPPING: Dict[BookFilterType, FilterDetails] = {
    BookFilterType.BOOK_SUMMARY: FilterDetails(
        table="book_metadata_v2",
        search_column="book_summary_embeddings",
        return_column="book_id",
        filter_title="Book summary details",
        select_columns=["book_id", "isbn", "title", "author_name", "publisher_name", "publication_date", "genre", "summary"],
        primary_key="book_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        select_exclude_columns=["book_id", "file_name", "summary"],
        search_type="semantic_search",
        fuzzy_features=["genre", "audience"],
        vector_weight=1,
        fuzzy_weight=0,
        similarity_threshold=0.3,
        filter_similarity_threshold=0.65
    ),
    BookFilterType.BOOK_TITLE: FilterDetails(
        table="book_metadata_v2",
        search_column="title_embeddings",
        return_column="book_id",
        filter_title="Book Title",
        select_columns=["book_id", "isbn", "title", "author_name", "publisher_name", "publication_date", "genre", "summary"],
        primary_key="book_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search"
    ),
    BookFilterType.AUTHOR_DETAILS: FilterDetails(
        table="book_author_v2",
        search_column="author_name_embeddings",
        return_column="book_id",
        filter_title="Author Details",
        select_columns=["book_id", "author_id", "author_name", "author_biography"],
        primary_key="book_id",
        mapping_type="single",
        filter_location="author_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        similarity_threshold=0.3,
        filter_similarity_threshold=0.65
    ),
    BookFilterType.GENRE_DETAILS: FilterDetails(
        table="book_metadata_v2",
        search_column="genre_embeddings",
        return_column="book_id",
        filter_title="Genre",
        select_columns=["book_id", "isbn", "title", "genre", "subgenre"],
        primary_key="book_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="hard_filter",
        search_type="semantic_search",
        similarity_threshold=0.3,
        filter_similarity_threshold=0.65
    ),
    BookFilterType.PUBLISHER_DETAILS: FilterDetails(
        table="book_metadata_v2",
        search_column="publisher_name_embeddings",
        return_column="book_id",
        filter_title="Publisher Details",
        select_columns=["book_id", "isbn", "title", "publisher_name", "publication_date"],
        primary_key="book_id",
        mapping_type="single",
        filter_location="book_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        similarity_threshold=0.3,
        filter_similarity_threshold=0.65
    ),
    BookFilterType.SUPPORTING_EXCERPTS: FilterDetails(
        table="book_excerpts_v2",
        search_column="excerpt_embeddings",
        return_column="book_id",
        filter_title="Supporting Excerpts",
        select_columns=["book_id", "excerpt_id", "excerpt_text", "excerpt_location"],
        primary_key="book_id",
        mapping_type="single",
        filter_location="excerpt_data",
        filter_mode="soft_filter",
        search_type="semantic_search",
        similarity_threshold=0.3,
        filter_similarity_threshold=0.65
    ),
}

