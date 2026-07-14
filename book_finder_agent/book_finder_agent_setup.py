from pydantic import Field
from typing import Optional, Tuple

from llm_studio_agents.AgentBase import AgentSetupBase


class BookFinderAgentSetup(AgentSetupBase):
    """
    Agent designed to retrieve books based on filters and a user query.
    Implements semantic and exact-match search across multiple book metadata dimensions.
    """

    # Response Behavior Configuration
    fallback_response: Optional[str] = Field(
        "I could not find matching book details right now. Please try with different search terms.",
        description="Response when no data is retrieved.",
        title="Fallback Response",
        UITab="Request and Response Behavior",
    )
    default_message_for_empty_llm_context: Optional[str] = Field(
        "No relevant books found for the selected filters. Please request different search terms.",
        description="LLM context message used when filters return no matching books. Supports <filter_type> and <filter_value> placeholders.",
        title="Empty Results Message",
        UITab="Request and Response Behavior",
    )
    show_headers: Optional[bool] = Field(
        False,
        description="Whether to show thinking/processing steps for this agent.",
        title="Show Headers",
        UITab="Request and Response Behavior",
    )
    smart_response_adjustment: Optional[bool] = Field(
        True,
        description="Toggle to allow downstream prompt adjustments and response post-processing.",
        title="Smart Response Adjustment",
        UITab="Request and Response Behavior",
    )
    generate_response_from_docs: Optional[bool] = Field(
        False,
        description="When enabled, LLM generates final response using retrieved books. When disabled, returns structured book data only.",
        title="Generate LLM Response",
        UITab="Request and Response Behavior",
    )

    # Retrieval Configuration
    books_per_result: Optional[int] = Field(
        5,
        description="Number of book rows to return from initial retrieval.",
        title="Books Per Result",
        ge=1, le=50,
        UITab="Retrieval Behavior",
    )
    max_books: Optional[int] = Field(
        10,
        description="Maximum number of unique books in the final response and context assembly.",
        title="Max Books",
        ge=1, le=100,
        UITab="Retrieval Behavior",
    )
    similarity_threshold: Optional[float] = Field(
        0.3,
        description="Minimum cosine similarity for book content and user query vectors.",
        title="Similarity Threshold",
        ge=0.0, le=1.0,
        UITab="Retrieval Behavior",
    )
    filter_similarity_threshold: Optional[float] = Field(
        0.65,
        description="Minimum similarity for specific attribute filters (author, genre, etc.).",
        title="Filter Similarity Threshold",
        ge=0.0, le=1.0,
        UITab="Retrieval Behavior",
    )
    max_chunks_to_use: Optional[int] = Field(
        6,
        description="Maximum number of manuscript chunks to include in LLM context.",
        title="Max Chunks",
        ge=1, le=20,
        UITab="Retrieval Behavior",
    )
    max_chunks_per_book: Optional[int] = Field(
        3,
        description="Maximum number of supporting chunks to retrieve per book.",
        title="Max Chunks Per Book",
        ge=1, le=10,
        UITab="Retrieval Behavior",
    )

    # Scoring Configuration
    context_weight_score: Optional[float] = Field(
        0.45,
        description="Weight for semantic similarity in final relevance scoring (0.0-1.0).",
        title="Context Weight",
        ge=0.0, le=1.0,
        UITab="Retrieval Behavior",
    )
    document_weight_score: Optional[float] = Field(
        0.25,
        description="Weight for document/filter overlap in final relevance scoring (0.0-1.0).",
        title="Document Weight",
        ge=0.0, le=1.0,
        UITab="Retrieval Behavior",
    )
    keyword_weight_score: Optional[float] = Field(
        0.30,
        description="Weight for keyword/n-gram frequency in final relevance scoring (0.0-1.0).",
        title="Keyword Weight",
        ge=0.0, le=1.0,
        UITab="Retrieval Behavior",
    )

    # Pagination Configuration
    default_show_more_length: Optional[int] = Field(
        3,
        description="Default number of books to return for show-more requests when length not specified.",
        title="Default Show More Length",
        ge=1, le=20,
        UITab="Retrieval Behavior",
    )
    max_show_more_books: Optional[int] = Field(
        20,
        description="Maximum number of books to store in session context for pagination.",
        title="Max Show More Books",
        ge=1, le=100,
        UITab="Retrieval Behavior",
    )

    # Parallel Processing Configuration
    max_workers_for_citation_generation: Optional[int] = Field(
        10,
        description="Maximum number of parallel workers for concurrent citation verification.",
        title="Max Citation Workers",
        ge=1, le=50,
        UITab="Request and Response Behavior",
    )

    # Embedding Configuration
    embedding_dimensions: Optional[int] = Field(
        1536,
        description="Dimension of embedding vectors for vector similarity search (1536 for Gemini embeddings).",
        title="Embedding Dimensions",
        UITab="Retrieval Behavior",
    )

    # Database Table Configuration
    book_summary_table: Optional[str] = Field(
        "book_summary_backup_2",
        description="Table name for book summary embeddings and metadata.",
        title="Book Summary Table",
        UITab="Retrieval Behavior",
    )
    book_content_table: Optional[str] = Field(
        "book_content_chunked_backup_2",
        description="Table name for chunked book content and manuscript text.",
        title="Book Content Table",
        UITab="Retrieval Behavior",
    )
    book_metadata_table: Optional[str] = Field(
        "book_metadata_backup_2",
        description="Table name for book metadata including genre, publisher, and attributes.",
        title="Book Metadata Table",
        UITab="Retrieval Behavior",
    )
    session_context_table: Optional[str] = Field(
        "retrieved_document_details",
        description="Table name for session-based pagination state and retrieved document context.",
        title="Session Context Table",
        UITab="Retrieval Behavior",
    )
    max_book_ids: Optional[int] = Field(
        300,
        description="Maximum total number of book IDs to retrieve across all filter pathways.",
        title="Max Book IDs",
        ge=1, le=1000,
        UITab="Retrieval Behavior",
    )

    # LLM Generation Configuration
    llm_model_name: Optional[str] = Field(
        "gemini-2.0-flash-001",
        description="LLM model to use for response generation. Examples: gemini-2.0-flash-001, gemini-1.5-pro, claude-3-opus.",
        title="LLM Model Name",
        UITab="LLM Configuration",
    )
    llm_temperature: Optional[float] = Field(
        0.7,
        description="LLM temperature for response generation. Lower values (0.0-0.5) produce more deterministic responses; higher values (0.7-1.0) produce more creative responses.",
        title="LLM Temperature",
        ge=0.0, le=1.0,
        UITab="LLM Configuration",
    )
    llm_max_tokens: Optional[int] = Field(
        1024,
        description="Maximum number of tokens in LLM-generated response.",
        title="LLM Max Tokens",
        ge=10, le=4000,
        UITab="LLM Configuration",
    )
    llm_top_p: Optional[float] = Field(
        0.95,
        description="LLM top-p (nucleus sampling) parameter for diversity control.",
        title="LLM Top-P",
        ge=0.0, le=1.0,
        UITab="LLM Configuration",
    )
    prompt_template: Optional[str] = Field(
        None,
        description="Custom prompt template for LLM invocation. Use {user_query} and {context} as placeholders. If not provided, a default template will be used.",
        title="Custom Prompt Template",
        UITab="LLM Configuration",
    )
    enable_streaming: Optional[bool] = Field(
        True,
        description="Enable streaming output from LLM for real-time response delivery.",
        title="Enable Streaming",
        UITab="LLM Configuration",
    )

