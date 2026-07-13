import logging
import json
from typing import Optional, Dict, List, Tuple
from pydantic import BaseModel, Field

from .book_finder_retrieval_utils import DatabaseRetrievalUtils


class PaginationContext(BaseModel):
    """
    Pydantic model for capturing pagination state and context.
    Used to track session-level pagination progress.
    """
    session_id: str = Field(..., description="Unique session identifier")
    question_id: Optional[str] = Field(default=None, description="Question identifier for filtering")
    page: int = Field(default=1, description="Current page number (1-indexed)")
    page_size: int = Field(default=10, description="Number of results per page")
    total_available: int = Field(default=0, description="Total number of available results")
    displayed_count: int = Field(default=0, description="Number of already-displayed results")
    undisplayed_count: int = Field(default=0, description="Number of undisplayed results")


class BookPaginationUtils:
    """
    Utility class for orchestrating session-based pagination and show-more functionality.
    
    Provides methods to:
    - Fetch cached book results from the session context table
    - Mark retrieved books as displayed to prevent duplicate pagination results
    - Handle pagination limits and offset calculations
    - Support fallback queries when primary question doesn't match
    """
    
    @staticmethod
    def _show_more_details(
        agent,
        session_id: str,
        page: int,
        question: str,
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None
    ) -> Tuple[List[Dict], Dict, int, str]:
        """
        Orchestrate pagination by fetching undisplayed documents from session context.
        
        Flow B — Shows more results from a previous query by retrieving cached documents
        from the session context table and marking them as displayed.
        
        Args:
            agent: BookFinderAgent instance with initialized sql_executor_tool and queries
            session_id: Session identifier for grouping results
            page: Page number for offset calculation (1-indexed)
            question: Original question to match in context table
            next_trace: Trace object for downstream tools
            trace: Current execution trace
            
        Returns:
            Tuple[List[Dict], Dict, int, str]:
                - retrieved_books: List of book dicts with metadata
                - doc_id_map: Mapping of doc_id to database record ID
                - total_available: Total count of documents for this session/question
                - effective_question: The question actually used (may differ if fallback applied)
        """
        logging.info(
            f"[Pagination] Starting show_more_details for session_id='{session_id}', "
            f"page={page}, question='{question}'"
        )
        
        try:
            # Step B1a: Fetch show-more documents from context table
            fetch_result = BookPaginationUtils._fetch_show_more_documents(
                agent=agent,
                session_id=session_id,
                question=question,
                next_trace=next_trace,
                trace=trace
            )
            
            displayed_docs = fetch_result["previously_displayed_documents"]
            undisplayed_docs = fetch_result["new_documents"]
            doc_id_map = fetch_result["doc_id_to_db_id_map"]
            total_available = fetch_result["total_documents_available"]
            effective_question = fetch_result.get("effective_question", question)
            
            logging.info(
                f"[Pagination] Fetched {len(displayed_docs)} displayed and {len(undisplayed_docs)} "
                f"undisplayed docs for session_id='{session_id}'"
            )
            
            # Check if we have any undisplayed documents to return
            if not undisplayed_docs:
                logging.warning(
                    f"[Pagination] No undisplayed documents available for session_id='{session_id}'. "
                    f"Returning empty list."
                )
                return [], {}, 0, effective_question
            
            # Step B1b: Extract book IDs from undisplayed documents
            book_ids_to_mark = [doc["book_id"] for doc in undisplayed_docs if "book_id" in doc]
            
            # Step B1c: Mark retrieved documents as displayed
            if book_ids_to_mark:
                BookPaginationUtils.mark_books_as_displayed(
                    agent=agent,
                    session_id=session_id,
                    question=effective_question,
                    book_ids=book_ids_to_mark,
                    next_trace=next_trace,
                    trace=trace
                )
                logging.info(
                    f"[Pagination] Marked {len(book_ids_to_mark)} books as displayed"
                )
            
            # Prepare retrieved books in normalized format for response assembly
            retrieved_books = []
            for doc in undisplayed_docs:
                try:
                    book_record = {
                        "book_id": doc.get("book_id"),
                        "title": doc.get("title"),
                        "authors": doc.get("authors"),
                        "genres": doc.get("genres"),
                        "isbn": doc.get("isbn"),
                        "publication_date": doc.get("publication_date"),
                        "summary": doc.get("summary"),
                        "publisher": doc.get("publisher"),
                        "audience": doc.get("audience"),
                        "supporting_excerpts": doc.get("supporting_excerpts"),
                        "relevance_score": doc.get("relevance_score", 0.0),
                    }
                    retrieved_books.append(book_record)
                except Exception as e:
                    logging.warning(
                        f"[Pagination] Skipping malformed book record: {e}"
                    )
            
            logging.info(
                f"[Pagination] Successfully retrieved {len(retrieved_books)} books for pagination"
            )
            
            return retrieved_books, doc_id_map, total_available, effective_question
            
        except Exception as e:
            logging.error(
                f"[Pagination] Error during show_more_details: {str(e)}",
                exc_info=True
            )
            # Return empty results on error instead of raising (allows graceful fallback)
            return [], {}, 0, question
    
    @staticmethod
    def _fetch_show_more_documents(
        agent,
        session_id: str,
        question: str,
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None
    ) -> Dict[str, any]:
        """
        Execute fetch_show_more_docs.sql to retrieve both displayed and undisplayed documents.
        
        Performs a single optimized query that:
        1. Fetches all displayed rows (is_displayed = TRUE)
        2. Fetches undisplayed rows (is_displayed = FALSE) up to page limit
        3. Returns total count of all documents for this session/question
        4. Falls back to the latest question in session if the provided question doesn't match
        
        Args:
            agent: BookFinderAgent instance
            session_id: Session identifier
            question: Question to match in context table
            next_trace: Trace object
            trace: Current execution trace
            
        Returns:
            Dict with keys:
                - previously_displayed_documents: List of already-shown books
                - new_documents: List of newly available undisplayed books
                - doc_id_to_db_id_map: Mapping of book_id to database row ID
                - total_documents_available: Total count for pagination state
                - effective_question: The question actually used (in case of fallback)
        """
        logging.info(
            f"[FetchShowMore] Fetching documents for session_id='{session_id}', "
            f"question='{question}'"
        )
        
        try:
            # Get page size from agent config
            page_size = agent.config.page_size
            
            # Try to fetch using the provided question
            fetch_query = agent.queries.get('fetch_show_more_docs', '')
            params = (
                session_id, question, page_size,
                session_id, question,
                session_id, question,
                agent.config.max_results_per_query
            )
            
            rows = DatabaseRetrievalUtils._execute_query(
                agent,
                query=fetch_query,
                commit=False,
                params=params,
                next_trace=next_trace,
                trace=trace
            )
            
            is_fallback = False
            effective_question = question
            
            # If no results, try fallback query using the latest question in the session
            if not rows:
                logging.info(
                    f"[FetchShowMore] No documents found for question='{question}'. "
                    f"Attempting fallback using latest session question."
                )
                is_fallback = True
                fallback_query = agent.queries.get('fallback_fetch_show_more_docs', '')
                fallback_params = (
                    session_id,
                    session_id, page_size,
                    session_id,
                    session_id,
                    agent.config.max_results_per_query
                )
                
                rows = DatabaseRetrievalUtils._execute_query(
                    agent,
                    query=fallback_query,
                    commit=False,
                    params=fallback_params,
                    next_trace=next_trace,
                    trace=trace
                )
                
                # Extract the actual question from fallback results
                if rows and rows[0].get("user_query"):
                    effective_question = rows[0]["user_query"]
                    logging.info(
                        f"[FetchShowMore] Fallback found documents for question='{effective_question}'"
                    )
            
            # Separate displayed vs undisplayed documents
            displayed_rows = [row for row in rows if row.get("is_displayed")]
            undisplayed_rows = [row for row in rows if not row.get("is_displayed")]
            
            # Build doc_id to database ID mapping for citation tracking
            doc_id_map = {row["book_id"]: row.get("id") for row in rows if row.get("book_id")}
            
            # Get total count from any row (all rows have the same total_count value)
            total_count = rows[0].get("total_count", 0) if rows else 0
            
            logging.info(
                f"[FetchShowMore] Retrieved {len(displayed_rows)} displayed and "
                f"{len(undisplayed_rows)} undisplayed documents. Total available: {total_count}"
            )
            
            return {
                "previously_displayed_documents": displayed_rows,
                "new_documents": undisplayed_rows,
                "doc_id_to_db_id_map": doc_id_map,
                "total_documents_available": total_count,
                "effective_question": effective_question,
                "is_fallback_used": is_fallback,
            }
            
        except Exception as e:
            logging.error(
                f"[FetchShowMore] Error fetching show more documents: {str(e)}",
                exc_info=True
            )
            return {
                "previously_displayed_documents": [],
                "new_documents": [],
                "doc_id_to_db_id_map": {},
                "total_documents_available": 0,
                "effective_question": question,
                "is_fallback_used": False,
            }
    
    @staticmethod
    def mark_books_as_displayed(
        agent,
        session_id: str,
        question: str,
        book_ids: List[str],
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None
    ) -> None:
        """
        Mark retrieved books as displayed (is_displayed = TRUE) in the session context table.
        
        Updates the book_finder_chat_data table to prevent the same books from being
        returned in subsequent pagination requests. Uses bulk UPDATE for efficiency.
        
        Args:
            agent: BookFinderAgent instance
            session_id: Session identifier
            question: Question being answered
            book_ids: List of book IDs to mark as displayed
            next_trace: Trace object
            trace: Current execution trace
            
        Returns:
            None (side-effect only)
        """
        logging.info(
            f"[MarkDisplayed] Marking {len(book_ids)} books as displayed for "
            f"session_id='{session_id}'"
        )
        
        try:
            if not book_ids:
                logging.warning("[MarkDisplayed] No book IDs provided")
                return None
            
            # Execute mark_books_as_displayed.sql template
            mark_query = agent.queries.get('mark_books_as_displayed', '')
            params = (session_id, question, book_ids)
            
            DatabaseRetrievalUtils._execute_query(
                agent,
                query=mark_query,
                commit=True,
                params=params,
                next_trace=next_trace,
                trace=trace
            )
            
            logging.info(
                f"[MarkDisplayed] Successfully marked {len(book_ids)} books as displayed"
            )
            
        except Exception as e:
            logging.error(
                f"[MarkDisplayed] Error marking books as displayed: {str(e)}",
                exc_info=True
            )
            # Don't raise — marking displayed is optional for retrieval success

