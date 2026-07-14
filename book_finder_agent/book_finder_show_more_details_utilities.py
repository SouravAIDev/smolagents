import logging
import re
import json
from collections import Counter
from typing import Optional, Dict, List, Any, Tuple

from book_finder_agent.book_finder_database_retrieval import DatabaseRetrievalUtils


class ShowMoreDetailsUtils:
    """Helpers for show-more book tracking and display state updates.
    
    Manages pagination workflows by tracking which books have been displayed
    and updating their display counts. Implements fallback logic when primary
    query results are empty, ensuring graceful degradation.
    """
    
    @staticmethod
    def extract_book_isbns_from_response(llm_response: str) -> List[str]:
        """
        Extract ISBNs from the LLM response using citation link patterns.
        Looks for ISBN values embedded in markdown citation links: [text](url?isbn=ISBN)
        
        Args:
            llm_response: The LLM response text
            
        Returns:
            List of extracted ISBN strings, deduplicated
        """
        try:
            # Pattern for ISBN in citations: [text](url?isbn=ISBN)
            pattern = r'\[.*?\]\(.*?isbn=([\w\-]+).*?\)'
            isbns = re.findall(pattern, llm_response, re.IGNORECASE)
            
            # Deduplicate
            isbns = list(set(isbns))
            logging.info(f"Extracted {len(isbns)} ISBNs from response")
            return isbns
        except Exception as e:
            logging.error(f"Error extracting ISBNs from response: {e}")
            return []

    @staticmethod
    def mark_books_as_displayed(
        agent: Any,
        book_isbns: Optional[List[str]],
        session_id: str,
        question: str,
        next_trace: Optional[Dict] = None,
        trace: Optional[Dict] = None
    ) -> None:
        """
        Marks given ISBN values as displayed=True and increments display_count
        in the session context table.
        
        Args:
            agent: The agent instance (contains config, queries, sql_executor_tool)
            book_isbns: List of ISBNs to mark as displayed
            session_id: Session identifier
            question: The question being answered
            next_trace: Optional trace handler for observability
            trace: Optional trace handler for observability
        """
        try:
            logging.info(f"Marking {len(book_isbns) if book_isbns else 0} books as displayed")
            
            if not book_isbns or not isinstance(book_isbns, (list, tuple)):
                logging.warning("No valid ISBNs provided for display state update")
                return None
            
            # Create a counter for duplicate ISBNs
            isbn_counts = Counter(book_isbns)

            # Build placeholders for parameterized query
            isbn_placeholders = ", ".join(["(%s, %s)"] * len(isbn_counts))

            # Get query template
            update_query_template = agent.queries.get("mark_books_as_displayed", "")
            
            if not update_query_template:
                logging.error("mark_books_as_displayed SQL template not found")
                return None

            # Format query with placeholders
            update_query = update_query_template.format(
                context_table=agent.config.session_context_table,
                values_clause=isbn_placeholders
            )

            # Build parameter list
            params = []
            for isbn, count in isbn_counts.items():
                params.extend([isbn, count])

            params.append(session_id)
            params.append(question)

            # Execute update
            DatabaseRetrievalUtils._execute_query(
                agent,
                update_query,
                commit=True,
                params=tuple(params),
                next_trace=next_trace,
                trace=trace,
            )
            logging.info(f"Successfully marked {len(isbn_counts)} unique ISBNs as displayed")
            
        except Exception as e:
            logging.error(f"Error marking books as displayed: {e}", exc_info=True)

    @staticmethod
    def fetch_show_more_documents(
        agent: Any,
        length: int,
        session_id: str,
        question: str,
        show_more_details: Optional[Dict] = None,
        next_trace: Optional[Dict] = None,
        trace: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Fetches context data from the database for the given session_id and question.
        Retrieves both displayed and undisplayed books, implementing a fallback
        mechanism if the primary query returns no results.

        Args:
            agent: The agent instance
            length: Number of undisplayed books to fetch
            session_id: Session identifier
            question: The question being answered
            show_more_details: Optional dict containing pagination metadata
            next_trace: Optional trace handler
            trace: Optional trace handler

        Returns:
            Dict with keys:
              - previously_displayed_books: List of already-displayed books
              - new_books: List of undisplayed books
              - isbn_to_db_id_map: Mapping of ISBN to database IDs
              - total_books_available: Total count of available books
        """
        try:
            is_fallback = False
            max_books = agent.config.max_show_more_books
            
            # Attempt primary query
            fetch_query = agent.queries.get('fetch_show_more_books', '')
            
            if not fetch_query:
                logging.error("fetch_show_more_books SQL template not found")
                return {
                    "previously_displayed_books": [],
                    "new_books": [],
                    "isbn_to_db_id_map": {},
                    "total_books_available": 0
                }
            
            params = (
                session_id, question, length,
                session_id, question,
                session_id, question,
                max_books
            )

            # Set streaming messages
            agent.sql_executor_tool.config.stream_start_message = f"Fetching more books for: '{question}'"
            agent.sql_executor_tool.config.stream_end_message = "Books retrieved successfully"
            
            rows = DatabaseRetrievalUtils._execute_query(
                agent,
                fetch_query,
                commit=False,
                params=params,
                skip_stream_message_reset=True,
                next_trace=next_trace,
                trace=trace
            )

            # Fallback query if primary returns empty
            if not rows:
                logging.info(f"No books found, executing fallback query for session: {session_id}")
                is_fallback = True
                fallback_fetch_query = agent.queries.get('fallback_fetch_show_more_books', '')
                
                if not fallback_fetch_query:
                    logging.error("fallback_fetch_show_more_books SQL template not found")
                    return {
                        "previously_displayed_books": [],
                        "new_books": [],
                        "isbn_to_db_id_map": {},
                        "total_books_available": 0
                    }
                
                fallback_params = (
                    session_id,
                    session_id, length,
                    session_id,
                    session_id,
                    max_books
                )
                agent.sql_executor_tool.config.stream_start_message = f"Fetching more books for: '{question}'"
                agent.sql_executor_tool.config.stream_end_message = "Books retrieved successfully"
                rows = DatabaseRetrievalUtils._execute_query(
                    agent,
                    fallback_fetch_query,
                    commit=False,
                    params=fallback_params,
                    skip_stream_message_reset=True,
                    next_trace=next_trace,
                    trace=trace
                )

            # Separate displayed and undisplayed books
            displayed_rows = [row for row in rows if row.get("is_displayed", False)]
            undisplayed_rows = [row for row in rows if not row.get("is_displayed", False)]

            # Build ISBN to database ID mapping
            isbn_to_db_id_map = {row.get("isbn"): row.get("id") for row in rows if row.get("isbn") and row.get("id")}

            logging.info(
                f"Fetched {len(displayed_rows)} displayed and {len(undisplayed_rows)} new books "
                f"for question='{question}' and session_id='{session_id}'."
            )

            # Get total count
            total_books_available = rows[0].get("total_count", 0) if rows else 0

            # Update question in show_more_details if using fallback
            if rows and is_fallback and show_more_details:
                show_more_details['question'] = rows[0].get("question")

            return {
                "previously_displayed_books": displayed_rows,
                "new_books": undisplayed_rows,
                "isbn_to_db_id_map": isbn_to_db_id_map,
                "total_books_available": total_books_available
            }

        except Exception as e:
            logging.error(f"Error fetching show more books: {str(e)}", exc_info=True)
            return {
                "previously_displayed_books": [],
                "new_books": [],
                "isbn_to_db_id_map": {},
                "total_books_available": 0
            }

    @staticmethod
    def process_show_more_request(
        agent: Any,
        user_query: str,
        show_more_details: Dict[str, Any],
        next_trace: Optional[Dict] = None,
        trace: Optional[Dict] = None
    ) -> Tuple[List[Dict], Dict, int, List[Dict], str]:
        """
        Process a complete show_more pagination request.
        Fetches additional books from the session context, optionally applying
        fallback logic if the primary query is empty.

        Args:
            agent: The agent instance
            user_query: The original user query
            show_more_details: Dict with pagination parameters (length, question)
            next_trace: Optional trace handler
            trace: Optional trace handler

        Returns:
            Tuple of (retrieved_books, isbn_map, total_available, displayed_books, question_used)
        """
        try:
            # Extract pagination parameters
            length_of_books = show_more_details.get("length")
            question_for_more_books = show_more_details.get("question", user_query)

            # Validate and coerce length
            try:
                length_of_books = int(length_of_books) if length_of_books else agent.config.default_show_more_length
            except (TypeError, ValueError):
                logging.warning(f"Invalid length value, using default: {agent.config.default_show_more_length}")
                length_of_books = agent.config.default_show_more_length

            session_id = agent.data.get('session_id', 'default_session')
            
            logging.info(
                f"Processing show_more request: fetching {length_of_books} books "
                f"for question='{question_for_more_books}' with session_id='{session_id}'"
            )

            # Fetch books from session context
            books_data = ShowMoreDetailsUtils.fetch_show_more_documents(
                agent,
                length=length_of_books,
                session_id=session_id,
                question=question_for_more_books,
                show_more_details=show_more_details,
                next_trace=next_trace,
                trace=trace
            )
            
            displayed_books = books_data.get("previously_displayed_books", [])
            new_books = books_data.get("new_books", [])
            isbn_map = books_data.get("isbn_to_db_id_map", {})
            total_books_available = books_data.get("total_books_available", 0)

            # Check if we have any results
            if not displayed_books and not new_books:
                logging.warning("[ShowMore] No books found in pagination request")
                raise RuntimeError("No show_more books available")

            # Build retrieved books list
            retrieved_books = []
            if agent.config.generate_response_from_docs:
                # Use only new undisplayed books
                books_to_process = new_books
            else:
                # Use previously displayed + new books
                books_to_process = displayed_books + new_books

            for book in books_to_process:
                try:
                    # Handle nested book data
                    retrieved_books.append({
                        "isbn": book.get("isbn"),
                        "context_score": book.get("context_score", 0.0),
                        "is_displayed": book.get("is_displayed", False),
                        "display_count": book.get("display_count", 1)
                    })
                except Exception as e:
                    logging.warning(f"[ShowMore] Skipping malformed book row: {e}")
                    continue

            logging.info(f"[ShowMore] Retrieved {len(retrieved_books)} books for pagination response")
            return retrieved_books, isbn_map, total_books_available, displayed_books, question_for_more_books

        except Exception as e:
            logging.warning(f"[ShowMore] Error processing show_more request: {str(e)}", exc_info=True)
            return [], {}, 0, [], ""

    @staticmethod
    def fetch_filtered_question_documents(
        agent: Any,
        next_trace: Optional[Dict] = None,
        trace: Optional[Dict] = None
    ) -> Tuple[List[Dict], Dict, int, List[Dict], str]:
        """
        When filtered_question=True, fetch documents from the session context table
        for the latest question under this session, then filter by selected filters.

        Args:
            agent: The agent instance
            next_trace: Optional trace handler
            trace: Optional trace handler

        Returns:
            Tuple of (retrieved_books, isbn_map, total_available, displayed_books, transformed_query)
        """
        try:
            session_id = agent.data.get('session_id', 'default_session')
            
            # Extract filter type from selected_filters
            filter_type = agent.selected_filters.get("filter_type", "") if agent.selected_filters else ""
            filter_values = agent.selected_filters.get("filter_values", []) if agent.selected_filters else []
            
            if not filter_type or not filter_values:
                logging.warning("[FilteredQuestion] filter_type or filter_values missing")
                return [], {}, 0, [], ""

            # Step 1: Get latest question for this session
            latest_question_query = agent.queries.get("fetch_latest_question_for_session", "")
            
            if not latest_question_query:
                logging.error("fetch_latest_question_for_session SQL template not found")
                return [], {}, 0, [], ""
            
            latest_question_query = latest_question_query.format(
                context_table=agent.config.session_context_table
            )
            rows = DatabaseRetrievalUtils._execute_query(
                agent,
                query=latest_question_query,
                params=(session_id,),
                commit=False,
                next_trace=next_trace,
                trace=trace,
            )
            
            if not rows:
                logging.warning(f"[FilteredQuestion] No question found for session_id='{session_id}'")
                return [], {}, 0, [], ""

            question = rows[0].get("question")
            logging.info(f"[FilteredQuestion] Latest question for session: '{question}'")

            # Step 2: Fetch and filter books by JSONB metadata
            fetch_filtered_query = agent.queries.get("fetch_filtered_question_documents", "")
            
            if not fetch_filtered_query:
                logging.error("fetch_filtered_question_documents SQL template not found")
                return [], {}, 0, [], ""
            
            # Normalize filter type (convert camelCase to snake_case)
            filter_type_normalized = re.sub(r'(?<!^)(?=[A-Z])', '_', filter_type).lower()
            
            fetch_filtered_query = fetch_filtered_query.format(
                context_table=agent.config.session_context_table,
                filter_type=filter_type_normalized
            )
            
            # Prepare parameters
            filter_values_lower = [v.lower() if isinstance(v, str) else v for v in filter_values]
            params = (session_id, question, filter_values_lower)
            
            rows = DatabaseRetrievalUtils._execute_query(
                agent,
                query=fetch_filtered_query,
                params=params,
                commit=False,
                next_trace=next_trace,
                trace=trace,
            )

            if not rows:
                logging.warning("[FilteredQuestion] No books matched the applied filters")
                return [], {}, 0, [], ""

            total_books_available = rows[0].get("total_count", len(rows)) if rows else 0
            isbn_map = {row.get("isbn"): row.get("id") for row in rows if row.get("isbn") and row.get("id")}

            # Build retrieved books list
            retrieved_books = []
            for row in rows:
                try:
                    retrieved_books.append({
                        "isbn": row.get("isbn"),
                        "context_score": row.get("context_score", 0.0),
                        "is_displayed": row.get("is_displayed", False),
                        "display_count": row.get("display_count", 1)
                    })
                except Exception as e:
                    logging.warning(f"[FilteredQuestion] Skipping malformed book row: {e}")
                    continue

            logging.info(f"[FilteredQuestion] Retrieved {len(retrieved_books)} books after filtering")

            # Construct transformed query for LLM
            filter_values_str = ", ".join(str(v) for v in filter_values)
            transformed_query = f"{question} Only show books with {filter_type} as {filter_values_str}"
            logging.info(f"[FilteredQuestion] Transformed query: '{transformed_query}'")

            return retrieved_books, isbn_map, total_books_available, [], transformed_query

        except Exception as e:
            logging.error(f"[FilteredQuestion] Error: {str(e)}", exc_info=True)
            return [], {}, 0, [], ""

