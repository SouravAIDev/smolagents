import logging
import json
import uuid
from typing import Annotated, Dict, Any, List, Optional, Tuple
from datetime import datetime

from llm_studio_agents.AgentBase import AgentBase, RecommendationAgentBase
from llm_studio_agents.utils.utils_traceability import AITrace
from llm_studio_agents.utils.utils import accumulator, process_config
from llm_studio_agents.utils.utils_agent_pubsub import send_streaming_response_to_pubsub

from book_finder_agent_setup import BookFinderAgentSetup
from book_finder_agent_trace import BookFinderAgentTrace
from book_helper import BookFilterType, FilterTypeSchema, BOOK_FILTER_MAPPING, FilterDetails
from database_retrieval_utils import DatabaseRetrievalUtils
from book_finder_utilities import BookFinderUtilities
from citation_helpers import CitationUtils
from show_more_details_utilities import ShowMoreDetailsUtils
from ai_summary_utils import AIEmbeddingUtils

from llm_studio_tools.sql_executor_tool import SQLExecutorTool
from llm_studio_tools.llm_configuration_tool import LLMConfigurationTool
from llm_studio_tools.semantic_similarity_tool import SemanticSimilarityTool
from llm_studio_tools.citation_tool import CitationTool


class BookFinderAgent_v2(
    RecommendationAgentBase,
    DatabaseRetrievalUtils,
    BookFinderUtilities,
    ShowMoreDetailsUtils,
    CitationUtils,
    AIEmbeddingUtils
):
    """
    Main Book Finder Agent orchestrating end-to-end book retrieval pipeline.
    
    Implements three execution flows:
    - Flow A: Standard semantic search with filters (A1-A5)
    - Flow B: Pagination using session context (B1)
    - Flow C: Pre-filtered queries on cached results (C1)
    
    Integrates multiple utility classes for database operations, data processing,
    citation management, session state handling, and embedding operations.
    """
    
    CONFIG_CLASS = BookFinderAgentSetup
    
    def setup(self, config: dict, data: Optional[dict] = None, **kwargs) -> dict:
        """
        Initialize agent with configuration and tools.
        
        A1: Runtime Environment Initialization & Dependency Preparation
        A2: Application Bootstrap & Service Registration
        
        Args:
            config: Agent configuration dictionary
            data: Optional input data containing user context
            **kwargs: Additional parameters (agent_id, etc.)
        
        Returns:
            Dictionary with setup status
        """
        super().setup(config=config)
        self.data = data or {}
        self.agent_id = kwargs.get('agent_id')
        
        logging.info(f"{self.__class__.__name__} setup initiated")
        
        # Initialize SQL Executor Tool for database queries
        sql_config = process_config(
            config=config.get("tools", {}).get(SQLExecutorTool.__name__, {}),
            sub_level="integrations"
        )
        self.sql_executor_tool = SQLExecutorTool(config=sql_config, data=self.data)
        
        # Initialize LLM Configuration Tool
        llm_config = process_config(
            config=config.get("tools", {}).get(LLMConfigurationTool.__name__, {}),
            sub_level="integrations"
        )
        self.llm_configuration_tool = LLMConfigurationTool(config=llm_config, data=self.data)
        
        # Initialize Semantic Similarity Tool for embeddings
        semantic_config = process_config(
            config=config.get("tools", {}).get(SemanticSimilarityTool.__name__, {}),
            sub_level="integrations"
        )
        self.semantic_similarity_tool = SemanticSimilarityTool(config=semantic_config, data=self.data)
        
        # Initialize Citation Tool
        citation_config = process_config(
            config=config.get("tools", {}).get(CitationTool.__name__, {}),
            sub_level="integrations"
        )
        self.citation_tool = CitationTool(config=citation_config, data=self.data)
        
        # Load SQL query templates
        self.queries = self._read_queries(self)
        
        # Set up streaming message templates for SQL operations
        self.original_sql_start_header_messages = self.sql_executor_tool.config.stream_start_message
        self.original_sql_end_header_messages = self.sql_executor_tool.config.stream_end_message
        self.original_format_columns = getattr(self.sql_executor_tool.config, 'format_columns', None)
        
        logging.info(f"{self.__class__.__name__} setup completed successfully")
        return {"status": "initialized"}
    
    @AITrace(BookFinderAgentTrace)
    def run(
        self,
        user_query: Annotated[str, "Natural language question about books"],
        author_details: Annotated[Optional[str], "Author name or biography to search"] = None,
        author_biography: Annotated[Optional[str], "Detailed author biographical information"] = None,
        book_title: Annotated[Optional[str], "Book title or keyword"] = None,
        book_summary: Annotated[Optional[str], "Book summary or description"] = None,
        book_publication_date_details: Annotated[Optional[Dict], "Publication date filter with condition and date"] = None,
        genre_details: Annotated[Optional[str], "Genre or category of books"] = None,
        audience_details: Annotated[Optional[str], "Target audience for the book"] = None,
        isbn_details: Annotated[Optional[str], "ISBN number"] = None,
        publisher_details: Annotated[Optional[str], "Publisher name"] = None,
        imprint_details: Annotated[Optional[str], "Imprint or subsidiary publisher"] = None,
        prize_details: Annotated[Optional[str], "Awards or prizes won by books"] = None,
        location_details: Annotated[Optional[str], "Geographic setting of the book"] = None,
        section_details: Annotated[Optional[str], "Book section, chapter, or part"] = None,
        character_details: Annotated[Optional[str], "Character names or descriptions"] = None,
        supporting_excerpts: Annotated[Optional[str], "Specific book excerpts or quotes"] = None,
        quotes_details: Annotated[Optional[str], "Famous quotes from books"] = None,
        show_more_details: Annotated[Optional[bool], "Request additional results from previous query"] = None,
        next_trace=None,
        trace=None,
    ) -> Tuple[str, List[Dict], List[Dict], bool]:
        """
        Main orchestration method implementing Flow A, Flow B, and Flow C.
        
        Args:
            user_query: Primary natural language query
            *_details: Optional filter parameters
            show_more_details: Pagination trigger for Flow B
            next_trace: Nested trace for downstream tools
            trace: Current execution trace
        
        Returns:
            Tuple of (response_text, retrieved_documents, citations, bypass_orchestrator_response)
        """
        try:
            # A3: Request Validation & Input Normalization
            self.user_query = user_query
            session_id = str(uuid.uuid4())
            
            # Collect and validate filter parameters
            filter_params = FilterTypeSchema(
                author_details=author_details,
                author_biography=author_biography,
                book_title=book_title,
                book_summary=book_summary,
                book_publication_date_details=book_publication_date_details,
                genre_details=genre_details,
                audience_details=audience_details,
                isbn_details=isbn_details,
                publisher_details=publisher_details,
                imprint_details=imprint_details,
                prize_details=prize_details,
                location_details=location_details,
                section_details=section_details,
                character_details=character_details,
                supporting_excerpts=supporting_excerpts,
                quotes_details=quotes_details
            )
            active_filters = filter_params.get_run_params()
            self.filters = active_filters
            self.is_intersection = len(active_filters) > 1
            
            logging.info(f"Active filters: {list(active_filters.keys())}")
            send_streaming_response_to_pubsub(
                data=self.data,
                text="",
                is_stream_end=False,
                thinking_break=True,
                header_message=f"Searching for books matching your query with {len(active_filters)} filters...",
                explainability_id=self.agent_id
            )
            
            # Determine execution flow
            if show_more_details:
                # B1: Session Context Retrieval & Pagination Orchestration (Flow B)
                return self._execute_flow_b(
                    session_id=session_id,
                    next_trace=next_trace,
                    trace=trace
                )
            elif active_filters:
                # C1: Filtered Context Retrieval & Query Transformation (Flow C)
                return self._execute_flow_c(
                    session_id=session_id,
                    active_filters=active_filters,
                    next_trace=next_trace,
                    trace=trace
                )
            else:
                # A1-A5: Standard Request Processing Flow (Flow A)
                return self._execute_flow_a(
                    session_id=session_id,
                    user_query=user_query,
                    next_trace=next_trace,
                    trace=trace
                )
        
        except Exception as e:
            logging.error(f"Error in {self.__class__.__name__}.run(): {e}", exc_info=True)
            self.error = str(e)
            return self.config.fallback_response, [], [], False
    
    def _execute_flow_a(
        self,
        session_id: str,
        user_query: str,
        next_trace=None,
        trace=None
    ) -> Tuple[str, List[Dict], List[Dict], bool]:
        """
        Flow A: Standard Request Processing (A1-A5)
        
        A4: Core Processing Orchestration & Database Retrieval
        A5: Content Retrieval, Scoring & Post-Processing
        """
        send_streaming_response_to_pubsub(
            data=self.data,
            text="",
            is_stream_end=False,
            thinking_break=True,
            header_message="Generating embeddings for semantic search...",
            explainability_id=self.agent_id
        )
        
        # Generate embedding for user query
        query_embedding = self.generate_embedding(
            text=user_query,
            trace=trace,
            next_trace=next_trace
        )
        
        if not query_embedding:
            logging.warning("Failed to generate query embedding")
            return self.config.fallback_response, [], [], False
        
        # Execute semantic search across all filter types
        filtered_books = {}
        book_id_scores = {}
        
        for filter_type, filter_config in BOOK_FILTER_MAPPING.items():
            try:
                # Skip if table not configured
                if not filter_config.table:
                    continue
                
                send_streaming_response_to_pubsub(
                    data=self.data,
                    text="",
                    is_stream_end=False,
                    thinking_break=False,
                    header_message=f"Searching {filter_config.filter_title}...",
                    explainability_id=self.agent_id
                )
                
                # Execute vector similarity search
                results = self._execute_semantic_search(
                    query_embedding=query_embedding,
                    filter_type=filter_type,
                    filter_config=filter_config,
                    next_trace=next_trace,
                    trace=trace
                )
                
                # Aggregate results
                for book in results:
                    book_id = book.get('book_id')
                    if book_id not in filtered_books:
                        filtered_books[book_id] = book
                        book_id_scores[book_id] = {'context_score': 0, 'document_score': 0, 'keyword_score': 0}
                    
                    # Accumulate relevance scores
                    if 'similarity_score' in book:
                        book_id_scores[book_id]['document_score'] = max(
                            book_id_scores[book_id]['document_score'],
                            book[.get('similarity_score', 0)
                        )
            
            except Exception as e:
                logging.error(f"Error searching {filter_type}: {e}", exc_info=True)
                continue
        
        # Calculate final relevance scores
        for book_id, scores in book_id_scores.items():
            filtered_books[book_id].update(scores)
        
        self.calculate_final_scores(
            books=filtered_books,
            context_weight=self.config.context_weight_score,
            document_weight=self.config.document_weight_score,
            keyword_weight=self.config.keyword_weight_score,
            chunk_boost=self.config.chunk_retrieval_document_boost
        )
        
        # Reduce to top-scoring books
        filtered_books = self.reduce_book_rows(
            filtered_books=filtered_books,
            threshold=self.config.reduce_books_rows_threshold,
            min_rows=self.config.min_documents_to_shortlist
        )
        
        # Retrieve supporting excerpts
        send_streaming_response_to_pubsub(
            data=self.data,
            text="",
            is_stream_end=False,
            thinking_break=True,
            header_message="Retrieving supporting excerpts...",
            explainability_id=self.agent_id
        )
        
        book_ids = list(filtered_books.keys())[:self.config.max_book_ids]
        excerpts = self._retrieve_excerpts(
            book_ids=book_ids,
            next_trace=next_trace,
            trace=trace
        )
        
        # Enrich books with excerpts
        for excerpt in excerpts:
            book_id = excerpt.get('book_id')
            if book_id in filtered_books:
                if 'supporting_excerpts' not in filtered_books[book_id]:
                    filtered_books[book_id]['supporting_excerpts'] = []
                filtered_books[book_id]['supporting_excerpts'].append(excerpt)
        
        # Store in session context for pagination
        retrieved_for_llm = self._process_filtered_data(
            filtered_books=filtered_books,
            sort_by_score=True
        )[:self.config.max_books_per_response]
        
        self.retrieved_for_llm = retrieved_for_llm
        self.insert_retrieved_documents(
            session_id=session_id,
            question=user_query,
            retrieved_documents=retrieved_for_llm,
            trace=trace,
            next_trace=next_trace
        )
        
        # Generate LLM response
        send_streaming_response_to_pubsub(
            data=self.data,
            text="",
            is_stream_end=False,
            thinking_break=True,
            header_message="Generating response...",
            explainability_id=self.agent_id
        )
        
        if self.config.generate_response_from_docs and retrieved_for_llm:
            # Format retrieved context for LLM
            formatted_context = self._format_datetimes_for_llm(retrieved_for_llm)
            
            # Generate response using LLM configuration
            llm_response = self.llm_configuration_tool.run(
                prompt=f"Based on the following books: {json.dumps(formatted_context)}\n\nAnswer: {user_query}",
                next_trace=next_trace,
                trace=trace
            )
            response = llm_response.get('response', self.config.fallback_response)
        else:
            response = self.config.default_message_for_empty_llm_context.format(
                filter_type=', '.join(self.filters.keys()) if self.filters else 'all filters'
            ) if retrieved_for_llm else self.config.fallback_response
        
        # Extract citations from response
        self.citations = self.extract_citations_from_response(
            response_text=response,
            retrieved_docs=retrieved_for_llm
        ) if hasattr(self, 'extract_citations_from_response') else []
        
        # Build score map for tracing
        self.score_map = {str(book['book_id']): {
            'final_score': book.get('final_score', 0),
            'document_score': book.get('document_score', 0)
        } for book in retrieved_for_llm}
        
        return response, retrieved_for_llm, self.citations, self.config.smart_response_adjustment
    
    def _execute_flow_b(
        self,
        session_id: str,
        next_trace=None,
        trace=None
    ) -> Tuple[str, List[Dict], List[Dict], bool]:
        """
        Flow B: Show-More Pagination (B1)
        Fetches previously cached results, marks as displayed.
        """
        send_streaming_response_to_pubsub(
            data=self.data,
            text="",
            is_stream_end=False,
            thinking_break=True,
            header_message="Fetching additional results...",
            explainability_id=self.agent_id
        )
        
        # Fetch undisplayed documents from session context
        undisplayed = self.fetch_undisplayed_books(
            session_id=session_id,
            limit=self.config.default_show_more_length,
            trace=trace,
            next_trace=next_trace
        )
        
        if undisplayed:
            # Mark as displayed
            book_ids_to_mark = [doc['book_id'] for doc in undisplayed]
            self.mark_books_as_displayed(
                session_id=session_id,
                book_ids=book_ids_to_mark,
                trace=trace,
                next_trace=next_trace
            )
            
            self.retrieved_for_llm = undisplayed
            response = f"Found {len(undisplayed)} additional books matching your query."
            self.citations = []
        else:
            response = "No additional results available."
            undisplayed = []
            self.citations = []
        
        return response, undisplayed, self.citations, False
    
    def _execute_flow_c(
        self,
        session_id: str,
        active_filters: Dict[str, Any],
        next_trace=None,
        trace=None
    ) -> Tuple[str, List[Dict], List[Dict], bool]:
        """
        Flow C: Pre-Filtered Questions (C1)
        Applies JSONB filters to previously retrieved session documents.
        """
        send_streaming_response_to_pubsub(
            data=self.data,
            text="",
            is_stream_end=False,
            thinking_break=True,
            header_message="Applying filters to previous results...",
            explainability_id=self.agent_id
        )
        
        # Fetch latest question for context
        latest_question = self.fetch_latest_question(
            session_id=session_id,
            trace=trace,
            next_trace=next_trace
        )
        
        # Fetch filtered documents from session context
        filtered_docs = self.fetch_filtered_documents(
            session_id=session_id,
            filters=active_filters,
            limit=self.config.max_show_more_books,
            trace=trace,
            next_trace=next_trace
        )
        
        if filtered_docs:
            response = f"Found {len(filtered_docs)} books matching your filters."
            self.retrieved_for_llm = filtered_docs
            self.citations = []
        else:
            response = "No books match your selected filters."
            filtered_docs = []
            self.citations = []
        
        return response, filtered_docs, self.citations, False
    
    def _execute_semantic_search(
        self,
        query_embedding: List[float],
        filter_type: BookFilterType,
        filter_config: FilterDetails,
        next_trace=None,
        trace=None
    ) -> List[Dict]:
        """
        Execute vector similarity search for a specific filter type.
        """
        threshold = filter_config.similarity_threshold or self.config.similarity_threshold
        
        query_text = f"""
        SELECT book_id, 1 - ({filter_config.search_column} <=> %s::vector) AS similarity_score
        FROM {filter_config.table}
        WHERE 1 - ({filter_config.search_column} <=> %s::vector) >= %s
        LIMIT %s
        """
        
        return self._execute_query(
            query=query_text,
            params=(query_embedding, query_embedding, threshold, self.config.books_per_result),
            filter_type=filter_type.value,
            filter_value=str(query_embedding)[:50],
            mapping=filter_config,
            trace=trace,
            next_trace=next_trace
        )
    
    def _retrieve_excerpts(
        self,
        book_ids: List[str],
        next_trace=None,
        trace=None
    ) -> List[Dict]:
        """
        Retrieve supporting excerpts for selected books.
        """
        if not book_ids:
            return []
        
        query_text = f"""
        SELECT book_id, excerpt_id, excerpt_text, excerpt_location, chapter_number
        FROM {self.config.book_excerpt_table}
        WHERE book_id = ANY(%s::uuid[])
        LIMIT %s
        """
        
        return self._execute_query(
            query=query_text,
            params=(book_ids, self.config.max_excerpts_per_book * len(book_ids)),
            trace=trace,
            next_trace=next_trace
        )
    
    @classmethod
    def get_setup_config(cls) -> dict:
        """
        Return agent configuration schema and required tools.
        Used by LLM Studio framework for agent registration.
        """
        return accumulator(
            cls.CONFIG_CLASS,
            cls.__name__,
            [
                SQLExecutorTool,
                LLMConfigurationTool,
                SemanticSimilarityTool,
                CitationTool
            ],
            "tools"
        )

