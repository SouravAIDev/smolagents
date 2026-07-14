from datetime import datetime, date
import re
import html
import copy
import math
import json
import logging
import traceback
import os
from typing import Any, Dict, List, Optional, Annotated, Literal, Tuple, Union
from pydantic import Field
from concurrent.futures import ThreadPoolExecutor, as_completed

from collections import Counter
from llm_studio_tools.sql_executor_tool import SQLExecutorTool
from llm_studio_tools.llm_configuration_tool import LLMConfigurationTool
from tools.semantic_similarity_tool import SemanticSimilarityTool
from tools.citation_tool import CitationTool

from llm_studio_agents.AgentBase import AgentSetupBase, AgentsTraceBase
from llm_studio_agents.utils.utils import process_config
from llm_studio_agents.utils.utils_traceability import AITrace
from llm_studio_agents.utils.utils_agent_pubsub import send_streaming_response_to_pubsub

from book_finder_agent.RecommendationAgentBase import RecommendationAgentBase
from llm_studio_agents.utils.utils import accumulator, process_config, citation_generator
from book_finder_agent.book_finder_helpers import BookFinderFilterType, FILTER_TABLE_MAPPING, FilterDetails, BookFinderRequestSchema
from book_finder_agent.book_finder_database_retrieval import DatabaseRetrievalUtils
from book_finder_agent.book_finder_utilities import BookFinderUtilities
from book_finder_agent.book_finder_session_helpers import SessionHelpers
from book_finder_agent.book_finder_citation_helpers import CitationUtils
from book_finder_agent.book_finder_llm_orchestration import BookFinderLLMOrchestration
from book_finder_agent.book_finder_citation_verification import CitationVerificationEngine
from book_finder_agent.book_finder_response_assembly import ResponseAssembly
from book_finder_agent.book_finder_retrieval_orchestration import RetrievalOrchestration
from book_finder_agent.book_finder_scoring_engine import ScoringEngine
from book_finder_agent.book_finder_show_more_details_utilities import ShowMoreDetailsUtils
from book_finder_agent.book_finder_flow_orchestration import FlowOrchestrator
from book_finder_agent.book_finder_response_finalizer import ResponseFinalizer

from book_finder_agent.book_finder_agent_setup import BookFinderAgentSetup
from book_finder_agent.book_finder_agent_trace import BookFinderAgentTrace

class InputValidationError(Exception):
    """Raised when mandatory input validation fails."""
    pass

class BookFinderAgent(RecommendationAgentBase):
    """
    Agent to retrieve book details and excerpts based on natural language queries.
    Implements a hybrid semantic + keyword search pipeline with session-aware pagination,
    multi-dimensional scoring, and citation-backed LLM generation.
    """

    CONFIG_CLASS = BookFinderAgentSetup

    def setup(
        self,
        concierge_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        config: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> dict:
        """Initialize agent tools, load SQL templates, and snapshot configuration."""
        super().setup(config=config)
        self.data = data or {}
        self.metadata = self.data.get("metadata", "{}") if data else "{}"
        self.metadata = json.loads(self.metadata) if isinstance(self.metadata, str) else self.metadata
        self.input_user_question = self.data.get("question")

        if self.data:
            self.data["hide_headers"] = not self.config.show_headers

        # Initialize SQL Executor Tool
        sql_executor_config = process_config(config=config["tools"][SQLExecutorTool.__name__], sub_level="integrations")
        self.sql_executor_tool = SQLExecutorTool(config=sql_executor_config, data=self.data)
        self.sql_executor_tool.config.show_results_in_end_header_message = True

        # Initialize LLM Configuration Tool
        llm_config_tool_config = process_config(config=config["tools"][LLMConfigurationTool.__name__], sub_level="integrations")
        self.llm_config_tool = LLMConfigurationTool(config=llm_config_tool_config, data=self.data)
        self.llm_config_tool_copy = copy.deepcopy(llm_config_tool_config)
        self.data_copy = copy.deepcopy(self.data)

        # Initialize Semantic Similarity Tool
        semantic_similarity_config = process_config(config=config["tools"][SemanticSimilarityTool.__name__], sub_level="integrations")
        self.semantic_similarity_tool = SemanticSimilarityTool(config=semantic_similarity_config, data=self.data)

        # Initialize Citation Tool
        citation_config = process_config(config=config["tools"][CitationTool.__name__], sub_level="integrations")
        self.citation_tool = CitationTool(config=citation_config, data=self.data)

        # Load SQL query templates from queries/ directory
        self.queries = DatabaseRetrievalUtils._read_queries(self)
        
        # Snapshot original SQL executor streaming messages for restoration
        self.original_sql_start_header_messages = self.sql_executor_tool.config.stream_start_message or ""
        self.original_sql_end_header_messages = self.sql_executor_tool.config.stream_end_message or ""
        self.original_format_columns = self.sql_executor_tool.config.format_result_columns or ""

        # Ensure session context table exists for pagination
        DatabaseRetrievalUtils.create_session_context_table(self)

        # Extract filter settings from metadata
        logging.info(f"Metadata: {self.metadata}")
        self.filtered_question = self.metadata.get("filtered_question", False)
        self.selected_filters = self.metadata.get("selected_filters", {})
        logging.info(f"filtered_question: {self.filtered_question}, selected_filters: {self.selected_filters}")

        # Initialize scoring weights
        self.context_weight_score = self.config.context_weight_score
        self.document_weight_score = self.config.document_weight_score
        self.keyword_weight_score = self.config.keyword_weight_score

        # Initialize table names from configuration
        self.book_summary_table = self.config.book_summary_table
        self.book_content_table = self.config.book_content_table
        self.book_metadata_table = self.config.book_metadata_table
        self.session_context_table = self.config.session_context_table

        logging.info(f"{self.__class__.__name__} setup complete.")
        return {}

    def _load_sql_templates(self) -> Dict[str, str]:
        """
        Load SQL query templates from the queries/ directory.
        Returns a dictionary mapping query names to SQL template strings.
        """
        queries = {}
        query_dir = os.path.join(os.path.dirname(__file__), 'queries')
        
        query_files = {
            'retrieve_book_vector_search': 'retrieve_book_vector_search.sql',
            'retrieve_book_chunks': 'retrieve_book_chunks.sql',
            'create_session_context_table': 'create_session_context_table.sql',
            'fetch_show_more_books': 'fetch_show_more_books.sql',
            'fetch_latest_question': 'fetch_latest_question.sql',
            'mark_books_as_displayed': 'mark_books_as_displayed.sql',
            'insert_retrieved_documents': 'insert_retrieved_documents.sql',
            'upsert_retrieved_documents': 'upsert_retrieved_documents.sql',
            'expire_old_context': 'expire_old_context.sql',
            'filter_query_with_metadata': 'filter_query_with_metadata.sql',
        }
        
        for query_name, filename in query_files.items():
            filepath = os.path.join(query_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    queries[query_name] = f.read()
                logging.info(f"Loaded SQL template: {query_name}")
            except FileNotFoundError:
                logging.warning(f"SQL template not found: {filepath}")
            except Exception as e:
                logging.error(f"Error loading SQL template {query_name}: {e}")
        
        return queries

    @AITrace(BookFinderAgentTrace)
    def run(
        self,
        user_query: Annotated[
            str,
            "User's natural language question asking for book information, summaries, excerpts, or details.",
        ],
        book_summary_details: Annotated[Optional[str], "Filter by book summary details."] = None,
        search_sentence: Annotated[Optional[str], "Filter by search sentence or supporting excerpts."] = None,
        genre_details: Annotated[Optional[str], "Filter by genre."] = None,
        quotes: Annotated[Optional[str], "Filter by notable quotes."] = None,
        audience_details: Annotated[Optional[str], "Filter by target audience."] = None,
        location_details: Annotated[Optional[str], "Filter by location details in the book."] = None,
        contributor_details: Annotated[Optional[str], "Filter by contributor (author/editor) details."] = None,
        character_details: Annotated[Optional[str], "Filter by character details."] = None,
        contributor_biography_details: Annotated[Optional[str], "Filter by contributor biography."] = None,
        prize_details: Annotated[Optional[str], "Filter by prize or awards."] = None,
        section_details: Annotated[Optional[str], "Filter by book section details."] = None,
        publisher_details: Annotated[Optional[str], "Filter by publisher details."] = None,
        imprint_details: Annotated[Optional[str], "Filter by imprint details."] = None,
        show_more_details: Annotated[Optional[Dict[str, Any]], "Optional pagination request with previously fetched results."] = None,
        next_trace=None,
        trace=None,
    ) -> Dict[str, Any]:
        """
        Main orchestration method. Validates input, routes request to appropriate flow (A/B/C),
        executes retrieval pipeline, generates LLM response, and verifies citations.
        
        Returns:
            Dict with keys: response_text (str), retrieved_books (list), citations (list), bypass_orchestrator_response (bool)
        """
        logging.info(f"Running BookFinderAgent with user_query: '{user_query}'")
        try:
            # Input Validation (Step A3)
            if not user_query or not user_query.strip():
                raise InputValidationError("User query cannot be empty")
            
            self.user_query = self.input_user_question or user_query
            self.show_more_details = show_more_details
            logging.info(f"Show_more_details: {self.show_more_details}")
            
            # Ensure chat history context exists
            if not self.data.get('chat_history'):
                logging.info("Chat history not found in data. Disabling pagination.")
                show_more_details = None

            # Build filters dictionary
            filters = {
                BookFinderFilterType.BOOK_SUMMARY_DETAILS: book_summary_details,
                BookFinderFilterType.SEARCH_SENTENCE: search_sentence,
                BookFinderFilterType.GENRE_DETAILS: genre_details,
                BookFinderFilterType.QUOTES: quotes,
                BookFinderFilterType.AUDIENCE_DETAILS: audience_details,
                BookFinderFilterType.LOCATION_DETAILS: location_details,
                BookFinderFilterType.CONTRIBUTOR_DETAILS: contributor_details,
                BookFinderFilterType.CHARACTER_DETAILS: character_details,
                BookFinderFilterType.CONTRIBUTOR_BIOGRAPHY_DETAILS: contributor_biography_details,
                BookFinderFilterType.PRIZE_DETAILS: prize_details,
                BookFinderFilterType.SECTION_DETAILS: section_details,
                BookFinderFilterType.PUBLISHER_DETAILS: publisher_details,
                BookFinderFilterType.IMPRINT_DETAILS: imprint_details,
            }

            # Determine request flow (Step A1/B1/C1)
            session_id = self.data.get('session_id', 'default_session')
            is_show_more = show_more_details is not None
            
            # Ensure session context table exists
            DatabaseRetrievalUtils.create_session_context_table(self, next_trace=next_trace, trace=trace)
            
            # Route to appropriate flow
            if is_show_more:
                logging.info("Flow B: Pagination request detected")
                response_data = self._execute_pagination_flow(session_id, show_more_details, next_trace, trace)
            elif self.filtered_question and self.selected_filters:
                logging.info("Flow C: Pre-filtered query detected")
                response_data = self._execute_filtered_flow(session_id, filters, next_trace, trace)
            else:
                logging.info("Flow A: Standard retrieval")
                response_data = self._execute_standard_flow(session_id, user_query, filters, next_trace, trace)

            return response_data

        except InputValidationError as e:
            logging.error(f"Input validation error: {e}")
            return {
                "response_text": self.config.fallback_response,
                "retrieved_books": [],
                "citations": [],
                "bypass_orchestrator_response": False,
            }
        except Exception as e:
            logging.error(f"Unhandled error in BookFinderAgent.run: {e}", exc_info=True)
            return {
                "response_text": self.config.fallback_response,
                "retrieved_books": [],
                "citations": [],
                "bypass_orchestrator_response": False,
            }

    def _execute_standard_flow(
        self,
        session_id: str,
        user_query: str,
        filters: Dict[BookFinderFilterType, Optional[str]],
        next_trace,
        trace,
    ) -> Dict[str, Any]:
        """
        Flow A: Standard Retrieval Pipeline
        Executes vector search, scoring, LLM generation, and citation verification.
        """
        try:
            logging.info("=== FLOW A: Standard Retrieval ===")
            
            # Step 1: Mark old session records as expired
            DatabaseRetrievalUtils.expire_old_context(self, session_id=session_id, next_trace=next_trace, trace=trace)
            
            # Step 2: Generate query embedding
            logging.info(f"Generating embedding for query: '{user_query}'")
            query_vector = self.semantic_similarity_tool.run(
                text=user_query,
                next_trace=next_trace,
                trace=trace,
            )
            if not query_vector:
                logging.warning("Failed to generate query embedding")
                return {
                    "response_text": "Unable to process your query. Please try again.",
                    "retrieved_books": [],
                    "citations": [],
                    "bypass_orchestrator_response": False,
                }
            
            # Step 3: Execute vector searches and deduplicate
            active_filters = {k: v for k, v in filters.items() if v is not None}
            logging.info(f"Active filters: {len(active_filters)}")
            
            retrieved_isbns = DatabaseRetrievalUtils.execute_vector_search(
                self,
                query_vector=query_vector,
                active_filters=active_filters,
                next_trace=next_trace,
                trace=trace,
            )
            
            if not retrieved_isbns:
                logging.info("No books found matching the query")
                return {
                    "response_text": self.config.fallback_response,
                    "retrieved_books": [],
                    "citations": [],
                    "bypass_orchestrator_response": False,
                }
            
            logging.info(f"Retrieved {len(retrieved_isbns)} unique books")
            
            # Step 4: Retrieve supporting chunks
            chunks = DatabaseRetrievalUtils.retrieve_chunks(
                self,
                query_vector=query_vector,
                isbns=retrieved_isbns,
                next_trace=next_trace,
                trace=trace,
            )
            logging.info(f"Retrieved {len(chunks)} supporting chunks")
            
            # Step 5: Calculate multi-dimensional scores
            scored_books = self._calculate_scores(retrieved_isbns, chunks, user_query)
            
            # Step 6: Rank and slice results
            top_books = sorted(scored_books, key=lambda x: x.get('final_score', 0), reverse=True)[:self.config.books_per_result]
            
            # Step 7: Format context for LLM
            context_text = self._format_context_for_llm(top_books, chunks)
            
            # Step 8: Generate LLM response
            llm_response = self._generate_llm_response(user_query, context_text, next_trace, trace)
            
            # Step 9: Verify citations in parallel
            verified_response, citations = self._verify_and_extract_citations(
                llm_response,
                top_books,
                chunks,
                next_trace,
                trace,
            )
            
            # Step 10: Persist session state
            DatabaseRetrievalUtils.insert_retrieved_documents(
                self,
                session_id=session_id,
                question=user_query,
                documents=top_books,
                next_trace=next_trace,
                trace=trace,
            )
            
            return {
                "response_text": verified_response,
                "retrieved_books": [self._format_book_for_output(b) for b in top_books],
                "citations": citations,
                "bypass_orchestrator_response": not self.config.smart_response_adjustment,
            }
            
        except Exception as e:
            logging.error(f"Error in standard flow: {e}", exc_info=True)
            return {
                "response_text": self.config.fallback_response,
                "retrieved_books": [],
                "citations": [],
                "bypass_orchestrator_response": False,
            }

    def _execute_pagination_flow(
        self,
        session_id: str,
        show_more_details: Dict[str, Any],
        next_trace,
        trace,
    ) -> Dict[str, Any]:
        """
        Flow B: Pagination Flow
        Fetches previously cached but undisplayed results from session context.
        """
        try:
            logging.info("=== FLOW B: Pagination ===")
            
            # Extract pagination parameters
            show_more_length = show_more_details.get('length', self.config.default_show_more_length)
            show_more_length = min(show_more_length, self.config.max_show_more_books)
            
            # Fetch undisplayed documents from session context
            more_books = DatabaseRetrievalUtils.fetch_show_more_books(
                self,
                session_id=session_id,
                length=show_more_length,
                next_trace=next_trace,
                trace=trace,
            )
            
            if not more_books:
                logging.info("No more documents available for pagination")
                return {
                    "response_text": "No additional results found.",
                    "retrieved_books": [],
                    "citations": [],
                    "bypass_orchestrator_response": False,
                }
            
            # Mark retrieved books as displayed
            isbns = [b.get('isbn') for b in more_books if b.get('isbn')]
            DatabaseRetrievalUtils.mark_books_as_displayed(
                self,
                session_id=session_id,
                isbns=isbns,
                next_trace=next_trace,
                trace=trace,
            )
            
            logging.info(f"Fetched {len(more_books)} additional books from pagination")
            
            return {
                "response_text": "Here are more results from your search.",
                "retrieved_books": [self._format_book_for_output(b) for b in more_books],
                "citations": [],
                "bypass_orchestrator_response": False,
            }
            
        except Exception as e:
            logging.error(f"Error in pagination flow: {e}", exc_info=True)
            return {
                "response_text": self.config.fallback_response,
                "retrieved_books": [],
                "citations": [],
                "bypass_orchestrator_response": False,
            }

    def _execute_filtered_flow(
        self,
        session_id: str,
        filters: Dict[BookFinderFilterType, Optional[str]],
        next_trace,
        trace,
    ) -> Dict[str, Any]:
        """
        Flow C: Pre-Filtered Query Flow
        Applies JSONB metadata filters to existing session records.
        """
        try:
            logging.info("=== FLOW C: Pre-Filtered Query ===")
            
            # Apply metadata filters to session context
            filtered_books = DatabaseRetrievalUtils.filter_context_by_metadata(
                self,
                session_id=session_id,
                filters=self.selected_filters,
                next_trace=next_trace,
                trace=trace,
            )
            
            if not filtered_books:
                logging.info("No books match the applied filters")
                return {
                    "response_text": self.config.default_message_for_empty_llm_context,
                    "retrieved_books": [],
                    "citations": [],
                    "bypass_orchestrator_response": False,
                }
            
            logging.info(f"Filtered to {len(filtered_books)} books")
            
            return {
                "response_text": f"Found {len(filtered_books)} books matching your filters.",
                "retrieved_books": [self._format_book_for_output(b) for b in filtered_books],
                "citations": [],
                "bypass_orchestrator_response": False,
            }
            
        except Exception as e:
            logging.error(f"Error in filtered flow: {e}", exc_info=True)
            return {
                "response_text": self.config.fallback_response,
                "retrieved_books": [],
                "citations": [],
                "bypass_orchestrator_response": False,
            }

    def _calculate_scores(
        self,
        isbns: List[str],
        chunks: List[Dict[str, Any]],
        user_query: str,
    ) -> List[Dict[str, Any]]:
        """
        Calculate multi-dimensional scores for retrieved books.
        Final Score = (0.45 * S_sim) + (0.25 * S_doc) + (0.30 * S_key)
        """
        scored_books = []
        
        for isbn in isbns:
            # Semantic Similarity Score (S_sim)
            relevant_chunks = [c for c in chunks if c.get('isbn') == isbn]
            if relevant_chunks:
                s_sim = sum(c.get('similarity_score', 0) for c in relevant_chunks) / len(relevant_chunks)
                s_sim = min(1.0, max(0.0, s_sim))  # Normalize to [0, 1]
            else:
                s_sim = 0.0
            
            # Document Overlap Score (S_doc)
            s_doc = 0.25 if relevant_chunks else 0.0
            
            # Keyword Frequency Score (S_key)
            combined_text = ' '.join(c.get('text', '') for c in relevant_chunks)
            s_key = BookFinderUtilities.calculate_keyword_score(user_query, combined_text)
            
            # Calculate Final Score
            final_score = (0.45 * s_sim) + (0.25 * s_doc) + (0.30 * s_key)
            
            scored_books.append({
                'isbn': isbn,
                'semantic_similarity_score': s_sim,
                'document_overlap_score': s_doc,
                'keyword_score': s_key,
                'final_score': final_score,
                'chunks': relevant_chunks,
            })
        
        return scored_books

    def _format_context_for_llm(
        self,
        books: List[Dict[str, Any]],
        chunks: List[Dict[str, Any]],
    ) -> str:
        """
        Format retrieved books and chunks into structured XML context for LLM.
        """
        context_parts = []
        
        for i, book in enumerate(books, 1):
            isbn = book.get('isbn', 'UNKNOWN')
            title = book.get('title', 'Untitled')
            
            # Get up to max_chunks_per_book chunks
            relevant_chunks = book.get('chunks', [])[:self.config.max_chunks_per_book]
            chunks_text = '\n'.join([
                f"<chunk id='{c.get('chunk_id', 'unknown')}'>{c.get('text', '')}</chunk>"
                for c in relevant_chunks
            ])
            
            book_context = f"""
<book>
  <isbn>{isbn}</isbn>
  <title>{title}</title>
  <retrieved_chunks>
{chunks_text}
  </retrieved_chunks>
</book>
"""
            context_parts.append(book_context)
        
        return "\n".join(context_parts)

    def _generate_llm_response(
        self,
        user_query: str,
        context: str,
        next_trace,
        trace,
    ) -> str:
        """
        Generate LLM response based on query and context.
        Uses gemini-2.0-flash-001 model by default.
        """
        try:
            # Build prompt with context
            system_prompt = f"""You are a helpful book recommendation assistant. 
Provide accurate, evidence-backed responses using the provided book excerpts.
Always cite the specific books and excerpts you reference.

Available Books Context:
{context}

Respond to the user's query using the provided context."""
            
            self.llm_config_tool.config.context = system_prompt
            
            # Call LLM
            response = self.llm_config_tool.run(
                query=user_query,
                next_trace=next_trace,
                trace=trace,
            )
            
            if not response:
                logging.warning("LLM returned empty response")
                return "Unable to generate response. Please try again."
            
            return response
            
        except Exception as e:
            logging.error(f"Error generating LLM response: {e}", exc_info=True)
            return "Unable to generate response at this time."

    def _verify_and_extract_citations(
        self,
        llm_response: str,
        books: List[Dict[str, Any]],
        chunks: List[Dict[str, Any]],
        next_trace,
        trace,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Extract citations from LLM response and verify them in parallel against source texts.
        Returns tuple of (verified_response_text, citations_list).
        """
        try:
            # Extract citations from response
            citations = CitationUtils.extract_citations_from_response(llm_response)
            
            if not citations:
                logging.info("No citations found in response")
                return llm_response, []
            
            logging.info(f"Extracted {len(citations)} citations from response")
            
            # Verify citations in parallel
            verified_citations = []
            with ThreadPoolExecutor(max_workers=min(self.config.max_workers_for_citation_generation, len(citations))) as executor:
                futures = {}
                
                for i, citation in enumerate(citations):
                    # Find source text for this citation
                    source_chunk = next(
                        (c for c in chunks if c.get('chunk_id') == citation.get('source_chunk_id')),
                        None
                    )
                    
                    if source_chunk:
                        future = executor.submit(
                            CitationUtils.verify_citation,
                            citation.get('cited_text', ''),
                            source_chunk.get('text', ''),
                        )
                        futures[future] = (i, citation)
                
                # Collect results
                for future in as_completed(futures):
                    idx, citation = futures[future]
                    try:
                        is_verified = future.result(timeout=10)
                        citation['verified'] = is_verified
                        if is_verified:
                            verified_citations.append(citation)
                    except Exception as e:
                        logging.warning(f"Citation verification failed for citation {idx}: {e}")
                        citation['verified'] = False
            
            # Strip unverified citations from response
            verified_response = CitationUtils.strip_unverified_citations(llm_response, verified_citations)
            
            return verified_response, verified_citations
            
        except Exception as e:
            logging.error(f"Error verifying citations: {e}", exc_info=True)
            return llm_response, []

    def _retrieve_ids(
        self,
        active_filters: Dict[BookFinderFilterType, Optional[str]],
        query_vector: List[float],
        next_trace,
        trace,
    ) -> Tuple[List[str], Dict[str, Dict], bool]:
        """Execute parallel vector similarity searches across active filters.
        Retrieves matching book ISBNs and metadata, deduplicates across pathways.
        Returns: Tuple of (isbn_list, metadata_dict, should_reduce_rows_flag)
        """
        try:
            logging.info(f"Executing retrieval across {len(active_filters)} active filters")
            filter_pathways = {}
            for filter_type, filter_value in active_filters.items():
                if filter_value is None:
                    continue
                filter_config = FILTER_TABLE_MAPPING.get(filter_type)
                if filter_config:
                    filter_pathways[filter_type.value] = {
                        'embedding': query_vector,
                        'filter_value': filter_value,
                        'similarity_threshold': getattr(filter_config, 'similarity_threshold', self.config.similarity_threshold),
                        'config': filter_config
                    }
            isbn_list, metadata_dict, should_reduce = RetrievalOrchestration._retrieve_ids(
                agent=self,
                filter_pathways=filter_pathways,
                max_book_ids=self.config.max_book_ids,
                ids_per_filter_strategy=self.config.ids_per_filter_strategy,
                next_trace=next_trace,
                trace=trace
            )
            logging.info(f"Retrieved {len(isbn_list)} unique books, should_reduce={should_reduce}")
            return isbn_list, metadata_dict, should_reduce
        except Exception as e:
            logging.error(f"Error in _retrieve_ids: {e}", exc_info=True)
            return [], {}, False

    def _retrieve_content(
        self,
        book_ids: List[str],
        query_vector: List[float],
        next_trace,
        trace,
    ) -> List[Dict]:
        """Retrieve supporting manuscript chunks for book candidates.
        Executes vector similarity search on book_content_chunked_backup_2 table.
        Returns: List of chunk dictionaries with text, scores, and metadata.
        """
        try:
            logging.info(f"Retrieving chunks for {len(book_ids)} books")
            chunks = RetrievalOrchestration._retrieve_content(
                agent=self,
                book_ids=book_ids,
                query_embedding=query_vector,
                next_trace=next_trace,
                trace=trace
            )
            logging.info(f"Retrieved {len(chunks)} chunks")
            return chunks
        except Exception as e:
            logging.error(f"Error in _retrieve_content: {e}", exc_info=True)
            return []

    def _post_process(
        self,
        chunks: List[Dict],
        metadata_dict: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """Merge retrieved chunks with metadata and normalize data.
        Integrates supporting chunk content with book metadata for scoring.
        Returns: Updated metadata_dict with chunk integration and normalized fields.
        """
        try:
            logging.info(f"Post-processing {len(metadata_dict)} books with {len(chunks)} chunks")
            updated_dict = RetrievalOrchestration._post_process(chunks, metadata_dict)
            logging.info(f"Post-processing complete")
            return updated_dict
        except Exception as e:
            logging.error(f"Error in _post_process: {e}", exc_info=True)
            return metadata_dict

    def _calculate_scores(
        self,
        metadata_dict: Dict[str, Dict],
        user_query: str,
        active_filter_count: int,
        next_trace=None,
        trace=None,
    ) -> Dict[str, Dict]:
        """Calculate multi-dimensional relevance scores for all book candidates.
        Applies semantic similarity, document overlap, and keyword frequency scoring.
        Returns: Ordered dictionary of ISBN -> scored book data, sorted by final_score DESC.
        """
        try:
            logging.info(f"Calculating scores for {len(metadata_dict)} books")
            weight_total = (
                self.config.context_weight_score +
                self.config.document_weight_score +
                self.config.keyword_weight_score
            )
            if abs(weight_total - 1.0) > 0.01:
                logging.warning(
                    f"Scoring weights do not sum to 1.0: {weight_total}. "
                    f"Weights: sim={self.config.context_weight_score}, "
                    f"doc={self.config.document_weight_score}, "
                    f"key={self.config.keyword_weight_score}"
                )
            scored_dict = RetrievalOrchestration._calculate_scores(
                metadata_dict,
                user_query,
                active_filter_count,
                weight_sim=self.config.context_weight_score,
                weight_doc=self.config.document_weight_score,
                weight_key=self.config.keyword_weight_score
            )
            if scored_dict:
                top_score = max((book.get('final_score', 0.0) for book in scored_dict.values()), default=0.0)
                logging.info(f"Scoring complete. Top score: {top_score:.4f}")
            return scored_dict
        except Exception as e:
            logging.error(f"Error in _calculate_scores: {e}", exc_info=True)
            return metadata_dict

    def _format_book_for_output(self, book: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a book dictionary for inclusion in the output response.
        """
        return {
            'isbn': book.get('isbn'),
            'title': book.get('title'),
            'final_score': book.get('final_score', 0.0),
            'chunks': book.get('chunks', []),
            'scores': {
                'semantic_similarity': book.get('semantic_similarity_score', 0.0),
                'document_overlap': book.get('document_overlap_score', 0.0),
                'keyword_frequency': book.get('keyword_score', 0.0),
            }
        }

    @classmethod
    def get_setup_config(cls) -> dict:
        """Return aggregated configuration schema for agent and all tools."""
        return accumulator(
            cls.CONFIG_CLASS,
            cls.__name__,
            [SQLExecutorTool, LLMConfigurationTool, SemanticSimilarityTool, CitationTool],
            "tools"
        )

