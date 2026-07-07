from pydantic import Field
from typing import Optional, Tuple

from llm_studio_agents.AgentBase import AgentSetupBase


class BookFinderAgentSetup(AgentSetupBase):
    """
    Agent designed to retrieve books based on filters and a user query.
    Provides configuration for book retrieval thresholds, limits, and scoring weights.
    """

    fallback_response: Optional[str] = Field(
        "I could not find matching book details right now.",
        description="Response when no data is retrieved.",
        UITab="Request and Response Behavior",
    )
    default_message_for_empty_llm_context: Optional[str] = Field(
        "No relevant books fetched for the selected <filter_type>, please request different filters.",
        description="LLM context message used when hard filters return no matching books. Supports <filter_type> and <filter_value> placeholders.",
        UITab="Request and Response Behavior",
    )
    show_headers: Optional[bool] = Field(
        False,
        description="Whether to show thinking steps for this agent.",
        UITab="Request and Response Behavior",
    )
    books_per_result: Optional[int] = Field(
        5,
        description="Number of book rows to return from retrieval.",
        UITab="Retrieval Behavior",
    )
    max_books_per_response: Optional[int] = Field(
        3,
        description="Maximum number of unique books in the final response.",
        UITab="Retrieval Behavior",
    )
    max_excerpts_per_book: Optional[int] = Field(
        5,
        description="Number of excerpts to fetch per book.",
        UITab="Retrieval Behavior",
    )
    similarity_threshold: Optional[float] = Field(
        0.3,
        description="Minimum similarity for main book text and user query.",
        UITab="Retrieval Behavior",
    )
    filter_similarity_threshold: Optional[float] = Field(
        0.65,
        description="Minimum similarity for specific attribute filters (Author, Publisher, etc.).",
        UITab="Retrieval Behavior",
    )
    max_chunks_to_use: Optional[int] = Field(
        6,
        description="Chunks to include in the context block.",
        UITab="Retrieval Behavior",
    )
    max_excerpts_per_book: Optional[int] = Field(
        3,
        description="Maximum number of supporting excerpts to retrieve per book.",
        ge=1,
        UITab="Retrieval Behavior",
    )
    smart_response_adjustment: Optional[bool] = Field(
        True,
        description="Toggle to allow downstream prompt adjustments.",
        UITab="Request and Response Behavior",
    )
    generate_response_from_docs: Optional[bool] = Field(
        False,
        description="When enabled, LLM generates final response using retrieved docs.",
        UITab="Request and Response Behavior",
    )
    max_workers_for_citation_generation: Optional[int] = Field(
        10,
        description="MAX number of parallel workers to be used for citation generation.",
        title="Max Workers for Citation Generation",
        UITab="Request and Response Behavior"
    )
    embedding_dimensions: Optional[int] = Field(
        1536,
        description="Dimension of embedding vectors for vector search.",
        UITab="Retrieval Behavior",
    )
    max_book_ids: Optional[int] = Field(
        300,
        description="Maximum number of book IDs to retrieve across all filters.",
        ge=1, le=1000,
        UITab="Request and Response Behavior"
    )
    context_table: Optional[str] = Field(
        "book_retrieved_document_details",
        description="Name of the table for storing retrieved document context.",
        UITab="Retrieval Behavior",
    )
    default_show_more_length: Optional[int] = Field(
        3,
        description="Default number of books to fetch when show_more_details length is not specified.",
        UITab="Retrieval Behavior",
    )
    max_show_more_books: Optional[int] = Field(
        20,
        description="Maximum number of books to store in show_more context.",
        UITab="Retrieval Behavior",
    )
    context_weight_score: Optional[float] = Field(
        0.5,
        description="Weight for context similarity in book matching.",
        UITab="Retrieval Behavior",
    )
    document_weight_score: Optional[float] = Field(
        0.2,
        description="Weight for document similarity in book matching.",
        UITab="Retrieval Behavior",
    )
    chunk_retrieval_document_boost: Optional[float] = Field(
        0.2,
        description="Additional document-score boost applied when supporting excerpts are retrieved for an item.",
        UITab="Retrieval Behavior",
    )
    keyword_weight_score: Optional[float] = Field(
        0.3,
        description="Weight for keyword similarity in book matching.",
        UITab="Retrieval Behavior",
    )
    organization_names: Optional[Tuple[str, ...]] = Field(
        (),
        title="Publisher Names",
        description="Publisher names to filter books by. Select one or more publishers.",
        isMultiSelect=True,
        enum=["HarperCollins", "Penguin Random House", "Simon & Schuster"],
        value=["HarperCollins", "Penguin Random House", "Simon & Schuster"]
    )

    organization_table: Optional[str] = Field(
        "book_publisher",
        description="The Publisher table name",
        title="Publisher Table",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    book_table: Optional[str] = Field(
        "book_metadata",
        description="The Book table name",
        title="Book Table",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    book_author_table: Optional[str] = Field(
        "book_author",
        description="The Book Author table name",
        title="Book Author Table",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    book_author_normalized_table: Optional[str] = Field(
        "book_author_normalized",
        description="The Book Author Normalized table name",
        title="Book Author Normalized Table",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    book_genre_table: Optional[str] = Field(
        "book_genre",
        description="The Book Genre table name",
        title="Book Genre Table",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    book_award_table: Optional[str] = Field(
        "book_award",
        description="The Book Award table name",
        title="Book Award Table",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    book_excerpt_table: Optional[str] = Field(
        "book_excerpt",
        description="The Book Excerpt table name",
        title="Book Excerpt Table",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    book_detail_soft_similarity_threshold: Optional[float] = Field(
        0.3,
        description="The Soft similarity threshold",
        title="Book Detail soft similarity threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    book_detail_hard_similarity_threshold: Optional[float] = Field(
        0.65,
        description="The Hard similarity threshold",
        title="Book Detail Hard similarity threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    author_detail_soft_similarity_threshold: Optional[float] = Field(
        0.3,
        description="The Soft similarity threshold",
        title="Author Details Table soft similarity threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    author_detail_hard_similarity_threshold: Optional[float] = Field(
        0.65,
        description="The Hard similarity threshold",
        title="Author Details Table Hard similarity threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    genre_detail_soft_similarity_threshold: Optional[float] = Field(
        0.3,
        description="The Soft similarity threshold",
        title="Genre Details Table soft similarity threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    genre_detail_hard_similarity_threshold: Optional[float] = Field(
        0.65,
        description="The Hard similarity threshold",
        title="Genre Details Table Hard similarity threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    award_detail_soft_similarity_threshold: Optional[float] = Field(
        0.3,
        description="The Soft similarity threshold",
        title="Award Details Table soft similarity threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    award_detail_hard_similarity_threshold: Optional[float] = Field(
        0.65,
        description="The Hard similarity threshold",
        title="Award Details Table Hard similarity threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    excerpt_detail_soft_similarity_threshold: Optional[float] = Field(
        0.3,
        description="The Soft similarity threshold",
        title="Excerpt Details Table soft similarity threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    excerpt_detail_hard_similarity_threshold: Optional[float] = Field(
        0.65,
        description="The Hard similarity threshold",
        title="Excerpt Details Table Hard similarity threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    reduce_books_rows_threshold: Optional[float] = Field(
        0.3,
        description="The Reduce Book Rows threshold",
        title="Reduce Book Rows threshold",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

    min_documents_to_shortlist: Optional[int] = Field(
        8,
        description="Number of rows to maintain when reduce threshold removes more rows",
        title="Number of rows to maintain threshold While Reducing rows",
        additionalProperties=True,
        UITab="Retrieval Behavior",
    )

