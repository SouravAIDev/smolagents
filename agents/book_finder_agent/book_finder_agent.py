import logging
import math
import re
from typing import Annotated, Optional, Dict, Any, Tuple, List
from llm_studio_agents.AgentBase import AgentBase
from llm_studio_agents.utils.utils import accumulator, process_config
from llm_studio_agents.utils.utils_traceability import AITrace
from llm_studio_tools.sql_executor_tool import SQLExecutorTool
from llm_studio_tools.semantic_similarity_tool import SemanticSimilarityTool

from book_finder_helpers import BookFinderRequestSchema, InputValidationError, validate_request
from .book_finder_setup import BookFinderAgentSetup
from .book_finder_trace import BookFinderAgentTrace
from .book_finder_filters import BookFilterType, FILTER_TABLE_MAPPING, FilterDetails
from .book_finder_retrieval_utils import DatabaseRetrievalUtils
from .book_finder_utilities import DatabaseUtility
from .book_finder_pagination_helpers import BookPaginationUtils
from .book_finder_filtering_helpers import BookFilteringUtils


class BookFinderAgent(AgentBase):
    """
    Book Finder Agent: Retrieves relevant book excerpts and metadata matching user queries.
    
    Implements a multi-stage retrieval pipeline:
    1. Request validation and input normalization (Step A3)
    2. Database retrieval with conditional filtering (Steps A4-A7)
    3. Result scoring and ranking (Step A8)
    4. LLM response generation and citation extraction (Shared A5·B1·C1)
    5. Pagination handling (Flow B) and filter-based refinement (Flow C)
    """
    
    CONFIG_CLASS = BookFinderAgentSetup
    
    def setup(self, config: dict, data: Optional[dict] = None, **kwargs) -> dict:
        """
        Initialize the Book Finder Agent with configuration and resources.
        
        Called once per request. Initializes composed tools, loads SQL templates,
        and snapshots any tool-level settings for per-call override.
        
        Args:
            config: Agent configuration dict (will be processed and passed via process_config)
            data: Shared request data containing session context and chat history
            **kwargs: Additional arguments (agent_id, etc.)
            
        Returns:
            dict: Empty dict (setup is side-effect only)
        """
        super().setup(config=config)
        self.data = data or {}
        self.agent_id = kwargs.get('agent_id')
        
        # Initialize SQLExecutorTool for database operations
        sql_executor_config = process_config(config=config["tools"][SQLExecutorTool.__name__], sub_level="integrations")
        self.sql_executor_tool = SQLExecutorTool(config=sql_executor_config, data=self.data)
        
        # Initialize SemanticSimilarityTool for embedding operations
        semantic_similarity_config = process_config(config=config["tools"][SemanticSimilarityTool.__name__], sub_level="integrations")
        self.semantic_similarity_tool = SemanticSimilarityTool(config=semantic_similarity_config, data=self.data)
        
        # Load SQL query templates from queries directory
        self.queries = DatabaseRetrievalUtils._read_queries(self)
        
        logging.info(f"{self.__class__.__name__} setup complete")
        return {}
    
    @AITrace(BookFinderAgentTrace)
    def run(
        self,
        user_query: Annotated[str, "The user's natural language question about books, authors, genres, quotes, or other book metadata."],
        session_id: Annotated[str, "Unique identifier for the user session, used for pagination and context caching."],
        book_summary_details: Annotated[Optional[str], "Optional filter to search within book summaries and descriptions."] = None,
        genre_details: Annotated[Optional[str], "Optional filter to narrow results by genre (e.g., 'Science Fiction', 'Mystery')."] = None,
        author_details: Annotated[Optional[str], "Optional filter to narrow results by author name or alias."] = None,
        publication_date_details: Annotated[Optional[Dict[str, Any]], "Optional filter for publication date range (e.g., {'start': 2000, 'end': 2023})."] = None,
        isbn_details: Annotated[Optional[str], "Optional filter to search by ISBN or ISBN-like identifier."] = None,
        publisher_details: Annotated[Optional[str], "Optional filter to narrow results by publisher name."] = None,
        audience_details: Annotated[Optional[str], "Optional filter by target audience (e.g., 'Young Adult', 'Academic')."] = None,
        is_show_more: Annotated[bool, "If True, retrieve undisplayed results from previous session (Flow B pagination)."] = False,
        is_filter_request: Annotated[bool, "If True, apply only the specified filters to previous results (Flow C filtering)."] = False,
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]], list, bool]:
        """
        Main execution entry point for the Book Finder Agent.
        
        Orchestrates the retrieval pipeline: validates input, executes appropriate flow
        (standard retrieval, pagination, or filtered refinement), and returns citations.
        
        Args:
            user_query: The user's search question
            session_id: Unique session identifier
            book_summary_details: Optional book summary filter
            genre_details: Optional genre filter
            author_details: Optional author filter
            publication_date_details: Optional publication date filter
            isbn_details: Optional ISBN filter
            publisher_details: Optional publisher filter
            audience_details: Optional audience filter
            is_show_more: Whether this is a pagination request
            is_filter_request: Whether this is a filter-only request
            next_trace: Trace object for downstream tools (forwarded by framework)
            trace: Current execution trace (forwarded by framework)
            
        Returns:
            Tuple[str, Optional[Dict[str, Any]], list, bool]:
                - response text (str): Natural language response or templated summary
                - retrieved_documents (Dict[str, Any] or None): Supporting book excerpts and metadata
                - citations (list): Extracted citations with source attribution
                - bypass_orchestrator_response (bool): If True, orchestrator uses response as-is without post-processing
        """
        try:
            # Step A3: Request Validation & Input Normalization
            logging.info(f"Processing Book Finder Agent request: query='{user_query}', session_id='{session_id}'")
            
            # Validate required fields at entry
            if not user_query or (isinstance(user_query, str) and not user_query.strip()):
                raise InputValidationError("Search query cannot be empty")
            
            if not session_id or (isinstance(session_id, str) and not session_id.strip()):
                raise InputValidationError("Session ID is required")
            
            # Store session ID for downstream use (pagination, context management)
            self.session_id = session_id.strip() if isinstance(session_id, str) else session_id
            self.user_query = user_query.strip() if isinstance(user_query, str) else user_query
            
            # Construct filters dictionary from optional parameters
            filters = {
                'book_summary_details': book_summary_details,
                'genre_details': genre_details,
                'author_details': author_details,
                'publication_date_details': publication_date_details,
                'isbn_details': isbn_details,
                'publisher_details': publisher_details,
                'audience_details': audience_details,
            }
            
            # Validate and normalize filters via Pydantic schema
            try:
                validated_schema = BookFinderRequestSchema(
                    search_query=self.user_query,
                    session_id=self.session_id,
                    **filters
                )
            except Exception as e:
                logging.error(f"Request validation error: {e}")
                raise
            
            # Extract only non-None filters for downstream retrieval logic
            self.filters = validated_schema.get_run_params()
            logging.info(f"Applied filters: {list(self.filters.keys()) if self.filters else 'none'}")
            
            # Log request metadata for observability
            logging.info(f"Request validated successfully. Session: {self.session_id}, Filters: {len(self.filters)}")
            
            # Check for Flow B — Pagination/Show-More Request
            if is_show_more:
                logging.info(
                    f"[Flow B] Pagination request detected. Routing to show_more flow for "
                    f"session_id='{self.session_id}'"
                )
                
                # Flow B: Skip Steps A4-A5, retrieve cached results directly
                pagination_books, doc_id_map, total_available, effective_question = (
                    BookPaginationUtils._show_more_details(
                        agent=self,
                        session_id=self.session_id,
                        page=1,
                        question=self.user_query,
                        next_trace=next_trace,
                        trace=trace
                    )
                )
                
                # If pagination returns no results, fall back to standard flow
                if not pagination_books:
                    logging.info(
                        f"[Flow B] No pagination results available. Falling back to standard retrieval."
                    )
                else:
                    # Prepare response for pagination results
                    response_text = f"Found {len(pagination_books)} additional books from previous search. "
                    
                    retrieved_documents = {
                        "books": pagination_books,
                        "chunks": [],
                        "book_count": len(pagination_books),
                        "chunk_count": 0,
                        "uuid_mapping": {},
                        "is_pagination": True,
                        "total_available": total_available,
                        "effective_question": effective_question,
                    }
                    
                    citations = []
                    
                    logging.info(
                        f"[Flow B] Pagination complete. Returning {len(pagination_books)} books "
                        f"to response assembly."
                    )
                    
                    return (
                        response_text,
                        retrieved_documents,
                        citations,
                        False
                    )
            
            # Check for Flow C — Filtered Context Retrieval
            elif self.filtered_question and self.selected_filters and not is_show_more:
                logging.info(
                    f"[Flow C] Filtered context retrieval detected. Routing to filter flow for "
                    f"session_id='{self.session_id}', filters={list(self.selected_filters.keys())}"
                )
                
                # Flow C: Skip Steps A4-A5, apply filters to cached results
                filtered_books, metadata_map, total_filtered, filter_contexts, transformed_query = (
                    BookFilteringUtils._fetch_filtered_question_documents(
                        agent=self,
                        session_id=self.session_id,
                        filters=self.selected_filters,
                        query=self.user_query,
                        next_trace=next_trace,
                        trace=trace
                    )
                )
                
                # If filtering returns no results, fall back to standard flow
                if not filtered_books:
                    logging.info(
                        f"[Flow C] No filtered results available. Falling back to standard retrieval."
                    )
                else:
                    # Prepare response for filtered results
                    filter_context_str = "; ".join(filter_contexts) if filter_contexts else "applied filters"
                    response_text = f"Found {len(filtered_books)} books matching your {filter_context_str}. "
                    
                    retrieved_documents = {
                        "books": filtered_books,
                        "chunks": [],
                        "book_count": len(filtered_books),
                        "chunk_count": 0,
                        "uuid_mapping": {},
                        "is_filtered": True,
                        "filter_contexts": filter_contexts,
                        "total_filtered": total_filtered,
                        "transformed_query": transformed_query,
                    }
                    
                    citations = []
                    
                    logging.info(
                        f"[Flow C] Filtered retrieval complete. Returning {len(filtered_books)} books "
                        f"to response assembly with transformed query: '{transformed_query}'"
                    )
                    
                    return (
                        response_text,
                        retrieved_documents,
                        citations,
                        False
                    )
            
            # Step A4: Core Processing Orchestration & Database Retrieval
            # Call _retrieve_ids() to orchestrate filter execution and ranking
            book_ids, filtered_books, should_reduce_rows = self._retrieve_ids(
                run_params=self.filters,
                user_query=self.user_query,
                next_trace=next_trace,
                trace=trace
            )
            
            logging.info(f"Retrieved {len(book_ids)} books after orchestration")
            
            # If no results from retrieval, return fallback response
            if not book_ids:
                logging.warning("No books found matching search criteria")
                return (
                    self.config.fallback_response,
                    None,
                    [],
                    False
                )
            
            # Step A5: Content Retrieval & Scoring
            # Get embedding of user query for chunk ranking
            query_embedding = self._get_embedding(
                self.user_query,
                next_trace=next_trace,
                trace=trace
            )
            
            # Retrieve supporting chunks for retrieved books
            chunks = self._retrieve_content(
                book_ids=book_ids,
                query_embedding=query_embedding,
                next_trace=next_trace,
                trace=trace
            )
            
            logging.info(f"Retrieved {len(chunks)} supporting chunks for {len(book_ids)} books")
            
            # Step A5: Content Retrieval, Scoring & Post-Processing
            # Calculate weighted relevance scores for all retrieved books
            scored_books = self._calculate_scores(
                filtered_books=filtered_books,
                query=self.user_query
            )
            
            logging.info(f"Calculated scores for {len(scored_books)} books")
            
            # Apply threshold filtering to remove low-relevance books
            if should_reduce_rows and scored_books:
                scored_books = self._reduce_contracts_based_on_threshold(
                    filtered_books=scored_books
                )
                logging.info(f"After filtering: {len(scored_books)} books remaining")
            
            # Transform scored books dict into ranked list and remove internal scoring fields
            from .book_finder_utilities import process_filtered_data
            ranked_books = process_filtered_data(scored_books)
            
            logging.info(f"Processed {len(ranked_books)} books into final ranked list")
            
            # Normalize datetime and UUID fields for LLM consumption
            from .book_finder_utilities import format_datetimes_for_llm
            
            # Extract book data dicts from the ranked list for normalization
            books_to_normalize = []
            for book_dict in ranked_books:
                for book_id, book_data in book_dict.items():
                    books_to_normalize.append(book_data)
            
            normalized_books, uuid_mapping = format_datetimes_for_llm(books_to_normalize)
            
            logging.info(f"Normalized {len(normalized_books)} books. UUID mapping size: {len(uuid_mapping)}")
            
            # Reconstruct ranked books with normalized data
            final_ranked_books = []
            for i, book_dict in enumerate(ranked_books):
                for book_id, book_data in book_dict.items():
                    if i < len(normalized_books):
                        final_ranked_books.append({book_id: normalized_books[i]})
            
            # Prepare response text summarizing retrieval results
            response_text = f"Found {len(final_ranked_books)} books matching your query. "
            response_text += f"Retrieved {len(chunks)} supporting excerpts. "
            
            # Prepare retrieved documents in the expected format
            retrieved_documents = {
                "books": final_ranked_books,
                "chunks": chunks,
                "book_count": len(final_ranked_books),
                "chunk_count": len(chunks),
                "uuid_mapping": uuid_mapping,
            }
            
            # Placeholder for citations (will be populated in ACT 11)
            citations = []
            
            return (
                response_text,
                retrieved_documents,
                citations,
                False
            )
            
        except InputValidationError as e:
            logging.error(f"Input validation error: {e}")
            # Input validation errors are allowed to propagate (will be caught by run.py for HTTP 400)
            raise
        except Exception as e:
            logging.error(f"Unexpected error in {self.__class__.__name__}: {e}", exc_info=True)
            # Return safe fallback for any other error (will result in HTTP 200 with fallback response)
            return (
                self.config.fallback_response,
                None,
                [],
                False
            )
    
    def _retrieve_ids(
        self,
        run_params: Dict[str, Any],
        user_query: str,
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None,
    ) -> Tuple[List[str], Dict[str, Dict], bool]:
        """
        Orchestrate filter execution and ranking to retrieve book IDs.
        
        Implements hierarchical filtering:
        1. Execute hard filters first to constrain result set
        2. Execute soft filters constrained by hard filter results
        3. Group results by book_id and aggregate scores
        4. Determine if results should be reduced due to volume
        
        Returns:
            Tuple of (book_ids, filtered_books_dict, should_reduce_rows)
        """
        logging.info(f"_retrieve_ids starting with run_params: {list(run_params.keys()) if run_params else 'none'}")
        
        all_results = {}
        hard_filter_book_ids = None
        deduplication_set = set()
        
        # Separate hard and soft filters
        hard_filters = {}
        soft_filters = {}
        
        ids_per_filter = math.ceil(self.config.max_results_per_query / len(run_params)) if run_params else 0
        
        for key, param_value in run_params.items():
            if param_value is None:
                continue
            
            # Find matching filter enum
            filter_enum = None
            for enum_member in BookFilterType:
                if enum_member.value == key:
                    filter_enum = enum_member
                    break
            
            if not filter_enum or filter_enum not in FILTER_TABLE_MAPPING:
                logging.warning(f"No table mapping found for parameter: {key}")
                continue
            
            filter_config = FILTER_TABLE_MAPPING[filter_enum]
            
            # Categorize as hard or soft filter
            if filter_config.filter_mode == "hard_filter":
                hard_filters[key] = (param_value, filter_enum, filter_config)
            else:
                soft_filters[key] = (param_value, filter_enum, filter_config)
        
        logging.info(f"Hard filters: {list(hard_filters.keys())}, Soft filters: {list(soft_filters.keys())}")
        
        should_reduce_rows = True
        
        # Step 1: Execute hard filters first to get book IDs
        if hard_filters:
            logging.info(f"Executing hard filters: {list(hard_filters.keys())}")
            for key, (param_value, filter_enum, filter_config) in hard_filters.items():
                try:
                    rows = self._execute_dynamic_filter(
                        filter_config=filter_config,
                        filter_value=param_value,
                        filter_enum=filter_enum,
                        limit=ids_per_filter,
                        next_trace=next_trace,
                        trace=trace
                    )
                    
                    current_book_ids = set()
                    if rows:
                        all_results[key] = rows
                        for row in rows:
                            book_id = row.get("book_id")
                            if book_id is not None:
                                current_book_ids.add(book_id)
                    
                    if hard_filter_book_ids is None:
                        hard_filter_book_ids = current_book_ids
                    else:
                        hard_filter_book_ids = hard_filter_book_ids.intersection(current_book_ids)
                    
                    logging.info(f"Hard filter '{key}' returned {len(current_book_ids)} unique book IDs, "
                               f"running total: {len(hard_filter_book_ids) if hard_filter_book_ids else 0}")
                except Exception as e:
                    logging.error(f"Failed to process hard filter {key}: {e}", exc_info=True)
            
            if not hard_filter_book_ids:
                logging.warning("No book IDs found from hard filters. Returning empty results.")
                return [], {}, should_reduce_rows
            
            # Filter all_results to only include books in hard_filter_book_ids
            for key in list(all_results.keys()):
                all_results[key] = [
                    row for row in all_results[key]
                    if row.get("book_id") in hard_filter_book_ids
                ]
        
        # Step 2: Execute soft filters, constrained by hard filter results
        if soft_filters:
            # Optimize for single soft filter case with no hard filters
            if hard_filters and len(soft_filters) == 1 and list(soft_filters.keys())[0] in ['book_summary_details', 'genre_details']:
                should_reduce_rows = False
            
            logging.info(f"Executing soft filters: {list(soft_filters.keys())}")
            for key, (param_value, filter_enum, filter_config) in soft_filters.items():
                try:
                    rows = self._execute_dynamic_filter(
                        filter_config=filter_config,
                        filter_value=param_value,
                        filter_enum=filter_enum,
                        hard_filter_book_ids=hard_filter_book_ids,
                        limit=ids_per_filter,
                        next_trace=next_trace,
                        trace=trace
                    )
                    
                    if rows:
                        all_results[key] = rows
                except Exception as e:
                    logging.error(f"Failed to process soft filter {key}: {e}", exc_info=True)
        
        # Step 3: Group results by book_id and aggregate scores
        grouped_books = self._group_contract_rows_by_filter(all_results)
        
        # Get unique book IDs
        book_ids = list(grouped_books.keys())
        logging.info(f"Retrieved {len(book_ids)} unique books from all filters")
        
        return book_ids, grouped_books, should_reduce_rows
    
    def _execute_dynamic_filter(
        self,
        filter_config: FilterDetails,
        filter_value: str,
        filter_enum: BookFilterType,
        hard_filter_book_ids: Optional[set] = None,
        limit: int = 10,
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute an individual filter query (either semantic or exact-match).
        
        Determines filter type (soft/hard) and constructs appropriate SQL query,
        executes it, and returns raw database results. Passes user_role to control
        database query timeouts (30s standard, 300s for admin/report).
        
        Args:
            filter_config: FilterDetails configuration for this filter type
            filter_value: User-provided filter value to search for
            filter_enum: BookFilterType enum identifying the filter
            user_role: Optional user role ('admin', 'report', or standard) for timeout determination
            hard_filter_book_ids: Optional set of book IDs to constrain soft filters
            limit: Maximum number of results to retrieve
            next_trace: Optional trace for downstream tools
            trace: Optional execution trace
            
        Returns:
            List[Dict]: Raw database result rows
        """
        logging.info(f"Executing {filter_enum.value} filter (mode={filter_config.filter_mode})")
        
        try:
            # Determine filter type and get embedding if needed
            query_embedding = None
            if filter_config.filter_mode == "soft_filter":
                # Get embedding for semantic search
                query_embedding = self._get_embedding(filter_value, next_trace=next_trace, trace=trace)
                if not query_embedding:
                    logging.warning(f"Failed to get embedding for soft filter {filter_enum.value}")
                    return []
            
            # Build join paths for many-to-many table relationships
            join_paths = DatabaseRetrievalUtils._build_join_paths(
                self,
                target_table=filter_config.table,
                target_filter_enum=filter_enum
            )
            
            # Construct parameterized SQL query
            sql_query, params = self._build_hybrid_search_query(
                table_name=filter_config.table,
                column_selections={filter_config.table: filter_config.select_columns},
                table_joins=join_paths,
                vector_features={filter_config.table: query_embedding} if query_embedding else {},
                fuzzy_features={filter_config.table: filter_value} if filter_config.filter_mode == "hard_filter" else {},
                condition_filters={},
                hard_filter_book_ids=hard_filter_book_ids,
                similarity_threshold=filter_config.similarity_threshold,
                limit=limit
            )
            
            # Execute query via DatabaseRetrievalUtils
            rows = DatabaseRetrievalUtils._execute_query(
                self,
                query=sql_query,
                params=tuple(params),
                filter_type=filter_enum.value,
                next_trace=next_trace,
                trace=trace
            )
            
            logging.info(f"Filter {filter_enum.value} returned {len(rows)} rows")
            return rows
            
        except Exception as e:
            logging.error(f"Error executing dynamic filter {filter_enum.value}: {e}", exc_info=True)
            return []
    
    def _build_hybrid_search_query(
        self,
        table_name: str,
        column_selections: Dict[str, List[str]],
        table_joins: List[Dict],
        vector_features: Dict[str, List[float]],
        fuzzy_features: Dict[str, str],
        condition_filters: Dict[str, Any],
        hard_filter_book_ids: Optional[set],
        similarity_threshold: float,
        limit: int = 100
    ) -> Tuple[str, List]:
        """
        Construct SQL query with hybrid semantic and exact-match scoring.
        
        Builds parameterized SQL that combines:
        - pgvector cosine similarity for embeddings (<=> operator)
        - PostgreSQL similarity() function for fuzzy text matching
        - Weighted final score calculation
        - Partitioned ROW_NUMBER() for ranking
        
        Args:
            table_name: Primary table to query
            column_selections: Dict mapping table → list of columns to SELECT
            table_joins: List of join definitions from _build_join_paths()
            vector_features: Dict mapping table → embedding vector for similarity
            fuzzy_features: Dict mapping table → search text for fuzzy matching
            condition_filters: Additional WHERE clause conditions
            hard_filter_book_ids: Optional set of book IDs for WHERE IN clause
            similarity_threshold: Minimum similarity score (0.0-1.0)
            limit: Maximum results to return
            
        Returns:
            Tuple of (sql_string, params_list) for parameterized execution
        """
        # Build SELECT clause
        select_parts = []
        for table, cols in column_selections.items():
            for col in cols:
                select_parts.append(f"t.{col}")
        
        # Add similarity score calculation if embedding provided
        if vector_features and table_name in vector_features:
            embedding = vector_features[table_name]
            if embedding:
                # Use pgvector <=> operator: distance = 1 - similarity
                select_parts.append(f"(1 - (t.{column_selections.get(table_name, ['embedding'])[0]} <=> %s::vector)) AS embedding_similarity")
        else:
            select_parts.append("0.0 AS embedding_similarity")
        
        select_sql = ",\n  ".join(select_parts)
        
        # Build FROM clause
        from_sql = f"FROM {table_name} t"
        
        # Build JOIN clauses
        join_sql = ""
        for join in table_joins:
            join_type = join.get("join_type", "LEFT OUTER")
            from_table = join.get("from_table")
            to_table = join.get("to_table")
            join_col_left = join.get("join_column_left")
            join_col_right = join.get("join_column_right")
            
            if from_table and to_table:
                join_sql += f"\n{join_type} JOIN {to_table} ON t.{join_col_left} = {to_table}.{join_col_right}"
        
        # Build WHERE clause
        where_conditions = []
        params = []
        
        # Add similarity threshold if semantic search
        if vector_features and table_name in vector_features:
            embedding = vector_features[table_name]
            if embedding:
                params.append(embedding)
                where_conditions.append(f"(1 - (t.{column_selections.get(table_name, ['embedding'])[0]} <=> %s::vector)) >= %s")
                params.append(similarity_threshold)
        
        # Add hard filter constraint if provided
        if hard_filter_book_ids:
            book_ids_list = list(hard_filter_book_ids)
            placeholders = ",".join(["%s"] * len(book_ids_list))
            where_conditions.append(f"t.book_id IN ({placeholders})")
            params.extend(book_ids_list)
        
        where_sql = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Build complete SQL query
        sql_query = f"""
            SELECT {select_sql}
            {from_sql}
            {join_sql}
            WHERE {where_sql}
            ORDER BY embedding_similarity DESC
            LIMIT %s
        """
        
        params.append(limit)
        
        return sql_query, params
    
    def _retrieve_content(
        self,
        book_ids: List[str],
        query_embedding: List[float],
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve supporting chunks for the provided books.
        
        Executes query to fetch manuscript excerpts associated with book IDs,
        ranked by cosine similarity to the query embedding using pgvector.
        Uses ROW_NUMBER() partitioned by book_id to select top N chunks per book.
        
        Args:
            book_ids: List of book IDs to retrieve chunks for
            query_embedding: Embedding vector of the user query for ranking
            next_trace: Optional trace for downstream tools
            trace: Optional execution trace
            
        Returns:
            List[Dict]: Supporting chunks with similarity scores
        """
        try:
            if not book_ids:
                return []
            
            # Get supporting chunks filter config
            filter_enum = BookFilterType.SUPPORTING_CHUNKS
            if filter_enum not in FILTER_TABLE_MAPPING:
                logging.warning("No table mapping found for chunks filter")
                return []
            
            chunk_config = FILTER_TABLE_MAPPING[filter_enum]
            target_table = chunk_config.table
            per_book_limit = self.config.page_size  # Use page_size as chunks per book
            
            # Build column selection
            selected_columns = list(chunk_config.select_columns)
            if "book_id" not in selected_columns:
                selected_columns.append("book_id")
            
            # Build similarity score expression
            if query_embedding:
                vector_literal = f"'[{",".join(map(str, query_embedding))}]'::vector"
                score_expr = f"(1 - (t0.{chunk_config.search_column} <=> {vector_literal})) AS final_score"
            else:
                score_expr = "0 AS final_score"
            
            # Build query with parameterized placeholders
            book_id_placeholders = ",".join(["%s"] * len(book_ids))
            columns_sql = ",".join(f"t0.{col}" for col in selected_columns)
            
            sql_query = f"""
                WITH base AS (
                    SELECT
                        {columns_sql},
                        {score_expr}
                    FROM {target_table} t0
                    WHERE t0.book_id IN ({book_id_placeholders})
                ),
                ranked_chunks AS (
                    SELECT *,
                        ROW_NUMBER() OVER (
                            PARTITION BY book_id
                            ORDER BY final_score DESC
                        ) AS rn
                    FROM base
                )
                SELECT * FROM ranked_chunks
                WHERE rn <= %s
            """
            
            params = book_ids + [per_book_limit]
            
            # Execute via DatabaseRetrievalUtils
            chunks = DatabaseRetrievalUtils._execute_query(
                self,
                query=sql_query,
                params=tuple(params),
                next_trace=next_trace,
                trace=trace,
            )
            
            logging.info(f"Retrieved {len(chunks)} chunks for {len(book_ids)} books")
            return chunks
            
        except Exception as e:
            logging.error(f"Error retrieving content: {e}", exc_info=True)
            return []
    
    def _get_embedding(
        self,
        text: str,
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None,
    ) -> List[float]:
        """
        Generate embedding vector for text using SemanticSimilarityTool.
        
        Args:
            text: Text to embed
            next_trace: Optional trace for downstream tools
            trace: Optional execution trace
            
        Returns:
            List[float]: Embedding vector, or empty list on failure
        """
        try:
            if not text or not isinstance(text, str) or not text.strip():
                logging.warning("Empty text provided to _get_embedding")
                return []
            
            # Call semantic similarity tool to get embedding
            result = self.semantic_similarity_tool.run(
                text=text.strip(),
                next_trace=next_trace,
                trace=trace,
            )
            
            # Extract embedding from result (assumes tool returns dict with 'embedding' key)
            if isinstance(result, dict):
                embedding = result.get("embedding") or result.get("vector")
                if isinstance(embedding, list):
                    return embedding
            elif isinstance(result, list):
                return result
            
            logging.warning(f"Unexpected embedding result type: {type(result)}")
            return []
            
        except Exception as e:
            logging.error(f"Error generating embedding: {e}", exc_info=True)
            # Return zero vector as fallback
            return [0.0] * 768  # Default embedding dimension
    
    def _group_contract_rows_by_filter(
        self,
        filter_results: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Group filter results by book_id and aggregate relevance scores.
        
        Deduplicates books across multiple filters and calculates weighted average
        score prioritizing primary fields (Title, Summary) over secondary fields (Genre, Audience).
        
        Args:
            filter_results: Dict mapping filter_name → list of result rows
            
        Returns:
            Dict mapping book_id → aggregated book record with scores
        """
        # Filter priority weights (higher = more important)
        FILTER_PRIORITY = {
            'book_title': 1.0,
            'book_summary': 0.9,
            'supporting_chunks': 0.8,
            'author_details': 0.7,
            'publisher_details': 0.6,
            'genre_details': 0.5,
            'audience_details': 0.4,
        }
        
        grouped = {}
        filter_match_count = {}
        
        # Aggregate results by book_id
        for filter_name, rows in filter_results.items():
            for row in rows:
                book_id = row.get("book_id")
                if not book_id:
                    continue
                
                # Initialize book record on first occurrence
                if book_id not in grouped:
                    # Parse the book record to normalize fields
                    grouped[book_id] = DatabaseUtility.parse_book_record(row)
                    grouped[book_id]["filter_matches"] = []
                    filter_match_count[book_id] = 0
                
                # Track which filters matched this book
                grouped[book_id]["filter_matches"].append(filter_name)
                filter_match_count[book_id] = len(set(grouped[book_id]["filter_matches"]))
                
                # Extract similarity score if present
                similarity_score = row.get("embedding_similarity", 0.0)
                if not isinstance(similarity_score, (int, float)):
                    similarity_score = 0.0
                
                # Apply filter priority weight to score
                weight = FILTER_PRIORITY.get(filter_name, 0.5)
                weighted_score = similarity_score * weight
                
                # Store weighted score for aggregation
                if "similarity_scores" not in grouped[book_id]:
                    grouped[book_id]["similarity_scores"] = []
                grouped[book_id]["similarity_scores"].append(weighted_score)
        
        # Calculate final relevance scores
        for book_id, book_data in grouped.items():
            # Average weighted similarity scores
            if "similarity_scores" in book_data and book_data["similarity_scores"]:
                avg_score = sum(book_data["similarity_scores"]) / len(book_data["similarity_scores"])
            else:
                avg_score = 0.0
            
            # Calculate final score using configured weights
            final_score = DatabaseUtility.calculate_relevance_score(
                embedding_similarity=avg_score,
                filter_match_count=filter_match_count.get(book_id, 0),
                max_filters=len(FILTER_PRIORITY),
                keyword_boost=0.0,
                embedding_weight=self.config.embedding_similarity_weight,
                filter_weight=self.config.filter_match_weight,
                keyword_weight=self.config.keyword_boost_weight
            )
            
            book_data["relevance_score"] = final_score
            book_data["embedding_similarity"] = avg_score
            book_data["filter_match_count"] = filter_match_count.get(book_id, 0)
            
            # Clean up temporary fields
            book_data.pop("similarity_scores", None)
        
        return grouped
    
    def _calculate_scores(
        self,
        filtered_books: Dict[str, Dict[str, Any]],
        query: str,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate weighted relevance scores for retrieved books.
        
        Computes final_score as a combination of context/similarity, document, and keyword scores.
        Final score is normalized to 0-100 percentage scale and books are sorted by score.
        
        Args:
            filtered_books: Dict of book_id -> book_data with similarity_score and filter_matches
            query: User query string for keyword scoring
            
        Returns:
            Dict mapping book_id -> book_data with final_score and context_score
        """
        try:
            score_map = {}  # Track all score components for debugging
            
            for book_id, book_data in filtered_books.items():
                # Extract component scores
                similarity_score = book_data.get("similarity_score", 0.0)
                if not isinstance(similarity_score, (int, float)):
                    similarity_score = 0.0
                similarity_score = max(0.0, min(1.0, similarity_score))
                
                # Document score: count of filters that matched (normalized to 0-1)
                filter_matches = book_data.get("filter_matches", [])
                document_score = len(set(filter_matches)) / max(len(FILTER_TABLE_MAPPING), 1)
                document_score = max(0.0, min(1.0, document_score))
                
                # Keyword score: ngram overlap
                keyword_score = self._ngram_search_with_weighted_reward(
                    query=query,
                    book_title=book_data.get("book_title", ""),
                    book_summary=book_data.get("book_summary", "")
                )
                keyword_score = max(0.0, min(1.0, keyword_score))
                
                # Combine weighted scores
                context_weight = self.config.embedding_similarity_weight
                document_weight = self.config.filter_match_weight
                keyword_weight = self.config.keyword_boost_weight
                
                final_score = (
                    context_weight * similarity_score +
                    document_weight * document_score +
                    keyword_weight * keyword_score
                )
                
                # Convert to percentage (0-100)
                final_score_percent = final_score * 100
                
                # Store scores
                book_data["final_score"] = final_score_percent
                book_data["context_score"] = final_score_percent
                
                score_map[book_id] = {
                    "similarity": similarity_score,
                    "document": document_score,
                    "keyword": keyword_score,
                    "final": final_score_percent
                }
                
                logging.info(f"Book {book_id}: similarity={similarity_score:.3f}, "
                           f"document={document_score:.3f}, keyword={keyword_score:.3f}, "
                           f"final={final_score_percent:.1f}")
            
            # Sort by final_score descending
            sorted_books = dict(sorted(
                filtered_books.items(),
                key=lambda x: x[1].get("final_score", 0),
                reverse=True
            ))
            
            logging.info(f"Calculated scores for {len(sorted_books)} books")
            return sorted_books
            
        except Exception as e:
            logging.error(f"Error calculating scores: {e}", exc_info=True)
            return filtered_books
    
    def _ngram_search_with_weighted_reward(
        self,
        query: str,
        book_title: str = "",
        book_summary: str = "",
        ngram_size: int = 2,
    ) -> float:
        """
        Calculate keyword match score using ngram overlap.
        
        Args:
            query: User query string
            book_title: Book title for high-weight matching
            book_summary: Book summary for lower-weight matching
            ngram_size: Size of ngrams (default: bigrams)
            
        Returns:
            float: Keyword score in range [0.0, 1.0]
        """
        try:
            if not query:
                return 0.0
            
            # Normalize text
            query = query.lower().strip()
            book_title = (book_title or "").lower().strip()
            book_summary = (book_summary or "").lower().strip()
            
            # Extract query ngrams
            query_words = re.findall(r'\w+', query)
            if len(query_words) < ngram_size:
                query_ngrams = set(query_words)
            else:
                query_ngrams = set()
                for i in range(len(query_words) - ngram_size + 1):
                    ngram = " ".join(query_words[i:i + ngram_size])
                    query_ngrams.add(ngram)
            
            if not query_ngrams:
                return 0.0
            
            # Count matches in title (weight: 0.7) and summary (weight: 0.3)
            title_matches = 0
            summary_matches = 0
            
            for ngram in query_ngrams:
                if ngram in book_title:
                    title_matches += 1
                if ngram in book_summary:
                    summary_matches += 1
            
            # Calculate weighted score
            total_ngrams = len(query_ngrams)
            title_score = (title_matches / total_ngrams) if total_ngrams > 0 else 0.0
            summary_score = (summary_matches / total_ngrams) if total_ngrams > 0 else 0.0
            
            keyword_score = (0.7 * title_score) + (0.3 * summary_score)
            return max(0.0, min(1.0, keyword_score))
            
        except Exception as e:
            logging.warning(f"Error in ngram search: {e}")
            return 0.0
    
    def _reduce_contracts_based_on_threshold(
        self,
        filtered_books: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Filter out low-relevance books based on threshold.
        
        Args:
            filtered_books: Dict of scored books
            
        Returns:
            Dict with low-relevance books removed (or preserved if minimum count enforced)
        """
        try:
            threshold = getattr(self.config, "reduce_contracts_rows_threshold", 0.3)
            min_count = getattr(self.config, "min_documents_to_shortlist", 8)
            
            logging.info(f"Filtering books with threshold={threshold}, min_count={min_count}")
            
            # Sort by score descending
            sorted_items = sorted(
                filtered_books.items(),
                key=lambda x: x[1].get("context_score", 0),
                reverse=True
            )
            
            # Separate books above and below threshold
            above_threshold = [
                (book_id, book_data) for book_id, book_data in sorted_items
                if book_data.get("context_score", 0) >= threshold
            ]
            
            below_threshold = [
                (book_id, book_data) for book_id, book_data in sorted_items
                if book_data.get("context_score", 0) < threshold
            ]
            
            # If above-threshold count is below minimum, add top below-threshold books
            if len(above_threshold) < min_count:
                needed = min_count - len(above_threshold)
                above_threshold.extend(below_threshold[:needed])
                removed_count = len(below_threshold) - needed
            else:
                removed_count = len(below_threshold)
            
            # Reconstruct dict
            result = dict(above_threshold)
            logging.info(f"Removed {removed_count} books below threshold. Kept {len(result)} books.")
            
            return result
            
        except Exception as e:
            logging.error(f"Error reducing books by threshold: {e}", exc_info=True)
            return filtered_books
    
    @classmethod
    def get_setup_config(cls) -> dict:
        """
        Aggregates the agent's configuration schema and all composed tool schemas.
        
        Used by /get_config endpoint to expose the full configuration document
        for settings UI and documentation tooling.
        
        Returns:
            dict: Aggregated configuration schema
        """
        return accumulator(
            cls.CONFIG_CLASS,
            cls.__name__,
            [SQLExecutorTool, SemanticSimilarityTool],  # Composed tools
            "tools"
        )
    
    def get_llm_config(self) -> dict:
        """
        Exposes just the LLM-specific slice of configuration.
        
        Used by /get_llm_config endpoint for tooling that only cares about
        model/prompt settings without the full agent configuration.
        
        Returns:
            dict: LLM-specific configuration slice
        """
        return {
            "llm_model": "gemini-2.0-flash",
            "llm_temperature": self.config.llm_temperature,
            "llm_max_tokens": self.config.llm_max_tokens,
            "enable_llm_generation": self.config.enable_llm_generation,
        }

