import logging
import json
from typing import Any, Dict, List, Optional, Tuple
from book_finder_agent.book_finder_database_retrieval import DatabaseRetrievalUtils
from book_finder_agent.book_finder_session_helpers import SessionHelpers


class FlowOrchestrator:
    """
    Routes requests to Flow A (Standard Retrieval), Flow B (Pagination),
    or Flow C (Pre-Filtered Query) based on request properties.
    Coordinates database retrieval, session management, and multi-dimensional scoring.
    """

    @staticmethod
    def determine_flow(
        show_more_details: Optional[Dict[str, Any]],
        selected_filters: Optional[Dict[str, str]],
        filtered_question: bool,
    ) -> str:
        """
        Determine which flow to execute based on request properties.
        Returns: 'A' (standard), 'B' (pagination), or 'C' (filtered)
        """
        if show_more_details is not None:
            return 'B'
        elif filtered_question and selected_filters:
            return 'C'
        else:
            return 'A'

    @staticmethod
    def execute_flow(
        agent,
        flow_type: str,
        user_query: str,
        session_id: str,
        query_embedding: Optional[List[float]],
        show_more_details: Optional[Dict[str, Any]],
        selected_filters: Optional[Dict[str, str]],
        active_filters: Dict,
        next_trace=None,
        trace=None,
    ) -> Tuple[List[Dict], Dict, int, List[Dict], str]:
        """
        Execute the appropriate flow based on flow_type.
        Returns: (retrieved_books, doc_id_to_db_id_map, total_available, previously_displayed, transformed_query)
        """
        try:
            if flow_type == 'A':
                logging.info("=== Executing Flow A: Standard Retrieval ===")
                return FlowOrchestrator._execute_flow_a(
                    agent, user_query, session_id, query_embedding,
                    active_filters, next_trace, trace
                )
            elif flow_type == 'B':
                logging.info("=== Executing Flow B: Pagination ===")
                return FlowOrchestrator._execute_flow_b(
                    agent, session_id, show_more_details, next_trace, trace
                )
            elif flow_type == 'C':
                logging.info("=== Executing Flow C: Pre-Filtered Query ===")
                return FlowOrchestrator._execute_flow_c(
                    agent, session_id, selected_filters, next_trace, trace
                )
            else:
                logging.error(f"Unknown flow type: {flow_type}")
                return [], {}, 0, [], user_query
        except Exception as e:
            logging.error(f"Error executing flow {flow_type}: {e}", exc_info=True)
            return [], {}, 0, [], user_query

    @staticmethod
    def _execute_flow_a(
        agent,
        user_query: str,
        session_id: str,
        query_embedding: List[float],
        active_filters: Dict,
        next_trace=None,
        trace=None,
    ) -> Tuple[List[Dict], Dict, int, List[Dict], str]:
        """
        Flow A: Standard Retrieval Pipeline
        - Expire old session context
        - Execute vector searches across active filters
        - Deduplicate ISBNs
        - Retrieve supporting chunks
        - Calculate multi-dimensional scores
        - Return top-ranked books
        """
        try:
            # Step 1: Expire old session context (A1)
            DatabaseRetrievalUtils._expire_old_context(
                agent, session_id=session_id, next_trace=next_trace, trace=trace
            )
            
            # Step 2-3: Execute vector searches and deduplicate (A2-A3)
            isbn_list, metadata_dict, should_reduce = agent._retrieve_ids(
                active_filters=active_filters,
                query_vector=query_embedding,
                next_trace=next_trace,
                trace=trace,
            )
            
            if not isbn_list:
                logging.warning("No books found in Flow A retrieval")
                return [], {}, 0, [], user_query
            
            logging.info(f"Retrieved {len(isbn_list)} books, should_reduce={should_reduce}")
            
            # Step 4: Retrieve supporting chunks (A4)
            chunks = agent._retrieve_content(
                book_ids=isbn_list,
                query_vector=query_embedding,
                next_trace=next_trace,
                trace=trace,
            )
            logging.info(f"Retrieved {len(chunks)} chunks")
            
            # Step 5: Post-process and merge chunks with metadata (A5 early)
            metadata_dict = agent._post_process(chunks, metadata_dict)
            
            # Step 6: Calculate multi-dimensional scores (A5 scoring)
            active_filter_count = len([f for f in active_filters.values() if f is not None])
            scored_dict = agent._calculate_scores(
                metadata_dict, user_query, active_filter_count,
                next_trace=next_trace, trace=trace
            )
            
            # Step 7: Slice to top results
            books_per_result = agent.config.books_per_result
            retrieved_books = sorted(
                scored_dict.values(),
                key=lambda x: x.get('final_score', 0.0),
                reverse=True
            )[:books_per_result]
            
            logging.info(f"Returning {len(retrieved_books)} top-ranked books")
            
            # Prepare doc_id_map and previously_displayed (empty for new search)
            doc_id_map = {b.get('isbn'): b.get('isbn') for b in retrieved_books}
            
            return retrieved_books, doc_id_map, len(retrieved_books), [], user_query
            
        except Exception as e:
            logging.error(f"Error in Flow A execution: {e}", exc_info=True)
            return [], {}, 0, [], user_query

    @staticmethod
    def _execute_flow_b(
        agent,
        session_id: str,
        show_more_details: Dict[str, Any],
        next_trace=None,
        trace=None,
    ) -> Tuple[List[Dict], Dict, int, List[Dict], str]:
        """
        Flow B: Pagination Pipeline (B1)
        - Fetch session context for current question
        - Retrieve undisplayed documents
        - Mark retrieved documents as displayed
        - Return paginated results
        """
        try:
            # Extract pagination parameters
            show_more_length = show_more_details.get('length', agent.config.default_show_more_length)
            show_more_length = min(show_more_length, agent.config.max_show_more_books)
            
            # Fetch the latest question for this session
            try:
                question = SessionHelpers.fetch_latest_question_for_session(
                    agent, session_id=session_id, next_trace=next_trace, trace=trace
                )
            except Exception:
                question = ""  # Fallback to empty query if fetch fails
            
            logging.info(f"Fetching show_more with length={show_more_length}")
            
            # Fetch undisplayed documents from session context
            result = DatabaseRetrievalUtils._fetch_show_more_documents(
                agent,
                length=show_more_length,
                session_id=session_id,
                question=question,
                next_trace=next_trace,
                trace=trace,
            )
            
            new_documents = result.get('new_documents', [])
            previously_displayed = result.get('previously_displayed_documents', [])
            doc_id_map = result.get('doc_id_to_db_id_map', {})
            total_available = result.get('total_documents_available', 0)
            
            if not new_documents:
                logging.info("No new documents available for pagination")
                return new_documents, doc_id_map, total_available, previously_displayed, question
            
            # Mark retrieved documents as displayed
            isbn_list = [d.get('isbn') for d in new_documents if d.get('isbn')]
            DatabaseRetrievalUtils._mark_contracts_as_displayed(
                agent, isbn_list, session_id, question,
                next_trace=next_trace, trace=trace
            )
            
            logging.info(f"Pagination returned {len(new_documents)} documents")
            return new_documents, doc_id_map, total_available, previously_displayed, question
            
        except Exception as e:
            logging.error(f"Error in Flow B execution: {e}", exc_info=True)
            return [], {}, 0, [], ""

    @staticmethod
    def _execute_flow_c(
        agent,
        session_id: str,
        selected_filters: Dict[str, str],
        next_trace=None,
        trace=None,
    ) -> Tuple[List[Dict], Dict, int, List[Dict], str]:
        """
        Flow C: Pre-Filtered Query Pipeline (C1)
        - Fetch latest question for session
        - Apply JSONB metadata filters to session context
        - Return filtered results without re-searching
        """
        try:
            # Fetch the latest question for this session
            try:
                question = SessionHelpers.fetch_latest_question_for_session(
                    agent, session_id=session_id, next_trace=next_trace, trace=trace
                )
            except Exception:
                question = ""  # Fallback to empty query if fetch fails
            
            logging.info(f"Filtering with selected_filters: {selected_filters}")
            
            # Fetch documents filtered by JSONB metadata
            result = DatabaseRetrievalUtils._fetch_filtered_question_documents(
                agent,
                session_id=session_id,
                selected_filters=selected_filters,
                next_trace=next_trace,
                trace=trace,
            )
            
            filtered_documents = result.get('filtered_documents', [])
            doc_id_map = result.get('doc_id_to_db_id_map', {})
            total_available = result.get('total_documents_available', 0)
            previously_displayed = result.get('previously_displayed_documents', [])
            
            logging.info(f"Filter returned {len(filtered_documents)} documents")
            return filtered_documents, doc_id_map, total_available, previously_displayed, question
            
        except Exception as e:
            logging.error(f"Error in Flow C execution: {e}", exc_info=True)
            return [], {}, 0, [], ""

