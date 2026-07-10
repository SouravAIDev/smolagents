from typing import Optional
from pydantic import BaseModel, Field
from llm_studio_agents.AgentBase import AgentSetupBase


class BookFinderAgentSetup(AgentSetupBase):
    """
    Configuration schema for the Book Finder Agent.
    Defines all tunable parameters including retrieval thresholds, weights, page sizes, and feature toggles.
    """
    
    # Fallback and Response Behavior
    fallback_response: Optional[str] = Field(
        default="I could not find matching book details at this time. Please refine your search query.",
        description="Response returned when no matching books are found or an error occurs.",
        title="Fallback Response",
    )
    
    # Retrieval Thresholds
    semantic_similarity_threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score for embedding-based retrieval (0.0-1.0).",
        title="Semantic Similarity Threshold",
    )
    
    citation_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for citation extraction (0.0-1.0).",
        title="Citation Confidence Threshold",
    )
    
    # Pagination and Result Limits
    max_results_per_query: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of book results to retrieve per query.",
        title="Max Results Per Query",
    )
    
    page_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of results to display per page in paginated responses.",
        title="Page Size",
    )
    
    show_more_batch_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of additional results to fetch on 'show more' requests.",
        title="Show More Batch Size",
    )
    
    # Session Management
    session_expiry_hours: int = Field(
        default=24,
        ge=1,
        description="Hours until session context is expired and removed from the database.",
        title="Session Expiry (hours)",
    )
    
    # Scoring Weights (must sum to 1.0)
    embedding_similarity_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for embedding similarity score in final relevance calculation (0.0-1.0).",
        title="Embedding Similarity Weight",
    )
    
    filter_match_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for filter match score in final relevance calculation (0.0-1.0).",
        title="Filter Match Weight",
    )
    
    keyword_boost_weight: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Weight for keyword boosting in final relevance calculation (0.0-1.0).",
        title="Keyword Boost Weight",
    )
    
    # Feature Toggles
    enable_semantic_search: bool = Field(
        default=True,
        description="Enable embedding-based semantic search for book retrieval.",
        title="Enable Semantic Search",
    )
    
    enable_exact_match_filter: bool = Field(
        default=True,
        description="Enable exact-match filtering on book metadata fields.",
        title="Enable Exact Match Filter",
    )
    
    enable_llm_generation: bool = Field(
        default=True,
        description="Enable LLM-based response generation. If False, returns templated summaries.",
        title="Enable LLM Generation",
    )
    
    enable_citation_generation: bool = Field(
        default=True,
        description="Enable citation extraction and formatting from LLM responses.",
        title="Enable Citation Generation",
    )
    
    # LLM Configuration
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature parameter for LLM generation (0.0-2.0, higher=more random).",
        title="LLM Temperature",
    )
    
    llm_max_tokens: int = Field(
        default=2048,
        ge=100,
        le=8192,
        description="Maximum tokens in LLM-generated response.",
        title="LLM Max Tokens",
    )
    
    # Smart Response Adjustment
    smart_response_adjustment: bool = Field(
        default=True,
        description="Enable smart adjustments to response formatting based on result count.",
        title="Smart Response Adjustment",
    )
    
    # Scoring and Filtering Thresholds
    reduce_contracts_rows_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Relevance score threshold (0.0-1.0) below which books are filtered out during post-processing.",
        title="Result Reduction Threshold",
    )
    
    min_documents_to_shortlist: int = Field(
        default=8,
        ge=1,
        le=100,
        description="Minimum number of books to keep even if below threshold to ensure sufficient context for LLM.",
        title="Minimum Documents to Keep",
    )
    
    class Config:
        extra = "forbid"
        title = "Book Finder Agent Configuration"
    
    def validate_weights(self) -> bool:
        """
        Validates that scoring weights sum to approximately 1.0 (within 0.01 tolerance).
        
        Returns:
            bool: True if weights are valid, False otherwise
        """
        total = self.embedding_similarity_weight + self.filter_match_weight + self.keyword_boost_weight
        return abs(total - 1.0) < 0.01

