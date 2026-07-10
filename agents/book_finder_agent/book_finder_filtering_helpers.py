import logging
from typing import Optional, Dict, List, Tuple, Any
from .book_finder_retrieval_utils import DatabaseRetrievalUtils


class BookFilteringUtils:
    """
    Utility class for orchestrating Flow C filtered context retrieval.
    
    Provides methods to:
    - Fetch the most recent question from a session
    - Apply JSONB-based filtering to cached results
    - Transform user queries to include filter context
    - Return pre-scored results directly to response assembly
    """
    
    @staticmethod
    def _fetch_filtered_question_documents(
        agent,
        session_id: str,
        filters: Dict[str, List[str]],
        query: str,
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None
    ) -> Tuple[List[Dict], Dict, int, List, str]:
        """
        Orchestrate filtered context retrieval by fetching cached documents
        from the session context table and applying JSONB filtering logic.
        
        Flow C — Applies structured UI filters to previous results by retrieving
        cached documents from the session context table and filtering them based
        on selected filter criteria (genres, authors, publisher, etc.).
        
        Args:
            agent: BookFinderAgent instance with initialized sql_executor_tool and queries
            session_id: Session identifier for scoping results
            filters: Dict of filter type -> list of selected values
                     E.g., {'genres': ['Fiction', 'Mystery'], 'publisher': ['Penguin']}
            query: Original user query for transformation
            next_trace: Trace object for downstream tools
            trace: Current execution trace
            
        Returns:
            Tuple[List[Dict], Dict, int, List, str]:
                - filtered_documents: List of book dicts matching filter criteria
                - metadata_mapping: Mapping of doc_id to metadata
                - total_filtered_count: Total count of documents after filtering
                - filter_contexts: List of filter descriptions for query transformation
                - transformed_query: Original query + filter context for LLM
        """
        logging.info(
            f"[Flow C] Starting filtered context retrieval for session_id='{session_id}', "
            f"filters={list(filters.keys())}"
        )
        
        try:
            # Step C1a: Fetch the most recent question from the session
            latest_question_result = BookFilteringUtils._fetch_latest_question(
                agent=agent,
                session_id=session_id,
                next_trace=next_trace,
                trace=trace
            )
            
            if not latest_question_result:
                logging.warning(
                    f"[Flow C] No previous question found in session '{session_id}'. "
                    f"Returning empty results."
                )
                return [], {}, 0, [], query
            
            question_id = latest_question_result[0].get('question_id')
            latest_user_query = latest_question_result[0].get('user_query', query)
            
            logging.info(
                f"[Flow C] Found latest question: question_id='{question_id}', "
                f"query='{latest_user_query}'"
            )
            
            # Step C1b: Apply JSONB filtering to cached documents
            filtered_documents = []
            metadata_mapping = {}
            filter_contexts = []
            
            # Iterate through each filter type and apply filtering
            for filter_type, filter_values in filters.items():
                if not filter_values or len(filter_values) == 0:
                    continue
                
                logging.info(
                    f"[Flow C] Applying filter: {filter_type} = {filter_values}"
                )
                
                # Execute fetch_filtered_question_documents.sql with filter criteria
                try:
                    filtered_result = BookFilteringUtils._fetch_documents_by_filter(
                        agent=agent,
                        session_id=session_id,
                        question_id=question_id,
                        filter_type=filter_type,
                        filter_values=filter_values,
                        next_trace=next_trace,
                        trace=trace
                    )
                    
                    if filtered_result:
                        filtered_documents.extend(filtered_result)
                        filter_contexts.append(
                            f"{filter_type.replace('_', ' ')}: {', '.join(filter_values)}"
                        )
                        logging.info(
                            f"[Flow C] Filter '{filter_type}' returned {len(filtered_result)} documents"
                        )
                except Exception as e:
                    logging.error(
                        f"[Flow C] Error applying filter '{filter_type}': {str(e)}",
                        exc_info=True
                    )
                    # Continue with next filter instead of failing entirely
                    continue
            
            # Deduplicate documents by book_id while preserving order
            seen_book_ids = set()
            unique_documents = []
            for doc in filtered_documents:
                book_id = doc.get('book_id')
                if book_id not in seen_book_ids:
                    seen_book_ids.add(book_id)
                    unique_documents.append(doc)
            
            # Sort by relevance_score descending
            unique_documents = sorted(
                unique_documents,
                key=lambda d: d.get('relevance_score', 0.0),
                reverse=True
            )
            
            logging.info(
                f"[Flow C] After deduplication and sorting: {len(unique_documents)} unique documents"
            )
            
            # Step C1c: Transform user query to include filter context
            transformed_query = query
            if filter_contexts:
                filter_context_str = "; ".join(filter_contexts)
                transformed_query = f"{query} [Filtered by: {filter_context_str}]"
                logging.info(
                    f"[Flow C] Transformed query: '{transformed_query}'"
                )
            
            # Prepare retrieved documents in normalized format
            retrieved_documents = []
            for doc in unique_documents:
                try:
                    book_record = {
                        "book_id": doc.get('book_id'),
                        "title": doc.get('title'),
                        "authors": doc.get('authors'),
                        "genres": doc.get('genres'),
                        "isbn": doc.get('isbn'),
                        "publication_date": doc.get('publication_date'),
                        "summary": doc.get('summary'),
                        "publisher": doc.get('publisher'),
                        "audience": doc.get('audience'),
                        "supporting_excerpts": doc.get('supporting_excerpts'),
                        "relevance_score": doc.get('relevance_score', 0.0),
                    }
                    retrieved_documents.append(book_record)
                    # Map doc_id to metadata for citation generation
                    metadata_mapping[doc.get('book_id')] = doc.get('metadata', {})
                except Exception as e:
                    logging.warning(
                        f"[Flow C] Skipping malformed document: {e}"
                    )
            
            logging.info(
                f"[Flow C] Successfully retrieved {len(retrieved_documents)} filtered documents"
            )
            
            return retrieved_documents, metadata_mapping, len(unique_documents), filter_contexts, transformed_query
            
        except Exception as e:
            logging.error(
                f"[Flow C] Error during filtered context retrieval: {str(e)}",
                exc_info=True
            )
            # Return empty results on error instead of raising (allows graceful fallback)
            return [], {}, 0, [], query
    
    @staticmethod
    def _fetch_latest_question(
        agent,
        session_id: str,
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None
    ) -> Optional[List[Dict]]:
        """
        Fetch the most recent question from a session.
        
        Args:
            agent: BookFinderAgent instance with sql_executor_tool
            session_id: Session identifier
            next_trace: Trace object for downstream tools
            trace: Current execution trace
            
        Returns:
            List[Dict] containing question_id, user_query, created_at; or None if not found
        """
        try:
            query = agent.queries.get('fetch_latest_question_for_session')
            if not query:
                logging.error("fetch_latest_question_for_session.sql template not loaded")
                return None
            
            result = agent.sql_executor_tool.run(
                sql_query=query,
                params=[session_id],
                next_trace=next_trace,
                trace=trace
            )
            
            logging.info(f"[Flow C] fetch_latest_question returned {len(result) if result else 0} records")
            return result if result else None
            
        except Exception as e:
            logging.error(
                f"[Flow C] Error fetching latest question: {str(e)}",
                exc_info=True
            )
            return None
    
    @staticmethod
    def _fetch_documents_by_filter(
        agent,
        session_id: str,
        question_id: str,
        filter_type: str,
        filter_values: List[str],
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None
    ) -> Optional[List[Dict]]:
        """
        Fetch documents from session context filtered by JSONB metadata criteria.
        
        Args:
            agent: BookFinderAgent instance with sql_executor_tool
            session_id: Session identifier
            question_id: Question identifier for scoping
            filter_type: Metadata key to filter on (e.g., 'genres', 'authors')
            filter_values: List of allowed values for the filter
            next_trace: Trace object for downstream tools
            trace: Current execution trace
            
        Returns:
            List[Dict] of filtered documents; or None on error
        """
        try:
            query = agent.queries.get('fetch_filtered_question_documents')
            if not query:
                logging.error("fetch_filtered_question_documents.sql template not loaded")
                return None
            
            # Build parameters list: session_id, question_id, then filter type/values repeated
            # The SQL uses CASE with multiple filter type checks, requiring duplicate params
            params = [
                session_id,
                question_id,
                filter_type,
                filter_values,
                filter_type,
                filter_values,
                filter_type,
                filter_values,
                filter_type,
                filter_values,
                filter_type,
                filter_values,
                100  # LIMIT
            ]
            
            result = agent.sql_executor_tool.run(
                sql_query=query,
                params=params,
                next_trace=next_trace,
                trace=trace
            )
            
            logging.info(
                f"[Flow C] fetch_documents_by_filter returned {len(result) if result else 0} records "
                f"for filter_type='{filter_type}'"
            )
            return result if result else None
            
        except Exception as e:
            logging.error(
                f"[Flow C] Error fetching filtered documents: {str(e)}",
                exc_info=True
            )
            return None

