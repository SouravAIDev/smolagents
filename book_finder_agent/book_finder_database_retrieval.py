import logging
import traceback
import os
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict

from book_finder_agent.book_finder_helpers import (
    BookFinderFilterType,
    FILTER_TABLE_MAPPING,
)


class DatabaseRetrievalUtils:
    """Database retrieval and query-template helpers for BookFinderAgent."""
    
    @staticmethod
    def _fetch_show_more_documents(agent, length, session_id, question, next_trace=None, trace=None):
        """
        Flow B: Fetch undisplayed documents from session context table.
        Returns dict with new_documents, previously_displayed_documents, doc_id_map, total_available.
        """
        try:
            fetch_query = agent.queries.get('fetch_show_more_books', '')
            if not fetch_query:
                logging.error("fetch_show_more_books SQL template not found")
                return {"new_documents": [], "previously_displayed_documents": [], "doc_id_to_db_id_map": {}, "total_documents_available": 0}
            
            params = (session_id, question, length, session_id, question, agent.config.max_show_more_books)
            rows = DatabaseRetrievalUtils._execute_query(
                agent, fetch_query, params=params, next_trace=next_trace, trace=trace
            )
            
            if not rows:
                return {"new_documents": [], "previously_displayed_documents": [], "doc_id_to_db_id_map": {}, "total_documents_available": 0}
            
            new_documents = [r for r in rows if not r.get("is_displayed")]
            previously_displayed = [r for r in rows if r.get("is_displayed")]
            doc_id_map = {r.get("isbn"): r.get("id") for r in rows if r.get("isbn")}
            total_available = rows[0].get("total_count", 0) if rows else 0
            
            return {
                "new_documents": new_documents,
                "previously_displayed_documents": previously_displayed,
                "doc_id_to_db_id_map": doc_id_map,
                "total_documents_available": total_available,
            }
        except Exception as e:
            logging.error(f"Error fetching show more documents: {e}", exc_info=True)
            return {"new_documents": [], "previously_displayed_documents": [], "doc_id_to_db_id_map": {}, "total_documents_available": 0}
    
    @staticmethod
    def _fetch_filtered_question_documents(agent, session_id, selected_filters, next_trace=None, trace=None):
        """
        Flow C: Fetch documents from session context filtered by JSONB metadata.
        Returns dict with filtered_documents, doc_id_map, total_available, previously_displayed.
        """
        try:
            filter_query = agent.queries.get('filter_query_with_metadata', '')
            if not filter_query:
                logging.error("filter_query_with_metadata SQL template not found")
                return {"filtered_documents": [], "doc_id_to_db_id_map": {}, "total_documents_available": 0, "previously_displayed_documents": []}
            
            # Build JSONB filter conditions from selected_filters dict
            import json
            filter_json = json.dumps(selected_filters)
            params = (session_id, filter_json, agent.config.max_show_more_books)
            
            rows = DatabaseRetrievalUtils._execute_query(
                agent, filter_query, params=params, next_trace=next_trace, trace=trace
            )
            
            if not rows:
                return {"filtered_documents": [], "doc_id_to_db_id_map": {}, "total_documents_available": 0, "previously_displayed_documents": []}
            
            filtered_documents = rows
            doc_id_map = {r.get("isbn"): r.get("id") for r in rows if r.get("isbn")}
            total_available = len(rows)
            previously_displayed = [r for r in rows if r.get("is_displayed")]
            
            return {
                "filtered_documents": filtered_documents,
                "doc_id_to_db_id_map": doc_id_map,
                "total_documents_available": total_available,
                "previously_displayed_documents": previously_displayed,
            }
        except Exception as e:
            logging.error(f"Error fetching filtered documents: {e}", exc_info=True)
            return {"filtered_documents": [], "doc_id_to_db_id_map": {}, "total_documents_available": 0, "previously_displayed_documents": []}
    
    @staticmethod
    def _mark_contracts_as_displayed(agent, contract_ids, session_id, question, next_trace=None, trace=None):
        """
        Mark contract/ISBN IDs as displayed in session context.
        """
        try:
            if not contract_ids:
                return
            
            mark_query = agent.queries.get('mark_books_as_displayed', '')
            if not mark_query:
                logging.warning("mark_books_as_displayed SQL template not found")
                return
            
            # Build placeholders for batch update
            placeholders = ", ".join(["(%s, %s)"] * len(contract_ids))
            mark_query = mark_query.format(placeholders=placeholders)
            
            params = []
            for cid in contract_ids:
                params.extend([cid, 1])  # increment count by 1
            params.extend([session_id, question])
            
            DatabaseRetrievalUtils._execute_query(
                agent, mark_query, params=tuple(params), commit=True,
                next_trace=next_trace, trace=trace
            )
        except Exception as e:
            logging.warning(f"Error marking contracts as displayed: {e}")
    
    @staticmethod
    def _upsert_retrieved_documents(agent, session_id, question, documents, next_trace=None, trace=None):
        """
        Persist retrieved documents to session context table for future pagination.
        Returns doc_id_map.
        """
        try:
            if not documents:
                return {}
            
            upsert_query = agent.queries.get('upsert_retrieved_documents', '')
            if not upsert_query:
                logging.warning("upsert_retrieved_documents SQL template not found")
                return {}
            
            # Build multi-row insert values
            placeholders = ", ".join(["(%s, %s, %s, %s, %s, %s)"] * len(documents))
            upsert_query = upsert_query.format(placeholders=placeholders)
            
            params = []
            doc_id_map = {}
            for i, doc in enumerate(documents):
                isbn = doc.get('isbn', '')
                context_score = doc.get('final_score', 0.0)
                chunk_ids = ','.join([str(c.get('chunk_id')) for c in doc.get('chunks', [])])
                
                params.extend([
                    session_id,
                    question,
                    isbn,
                    context_score,
                    False,  # is_displayed
                    chunk_ids or '',
                ])
                doc_id_map[isbn] = f"doc_{session_id}_{i}"
            
            DatabaseRetrievalUtils._execute_query(
                agent, upsert_query, params=tuple(params), commit=True,
                next_trace=next_trace, trace=trace
            )
            
            return doc_id_map
        except Exception as e:
            logging.error(f"Error upserting documents: {e}", exc_info=True)
            return {}
    
    @staticmethod
    def _expire_old_context(agent, session_id, next_trace=None, trace=None):
        """
        Mark old session context records as expired.
        """
        try:
            expire_query = agent.queries.get('expire_old_context', '')
            if not expire_query:
                logging.warning("expire_old_context SQL template not found")
                return
            
            params = (session_id,)
            DatabaseRetrievalUtils._execute_query(
                agent, expire_query, params=params, commit=True,
                next_trace=next_trace, trace=trace
            )
        except Exception as e:
            logging.warning(f"Error expiring old context: {e}")

    @staticmethod
    def _read_queries(agent_instance) -> Dict[str, str]:
        """
        Load SQL query templates from the queries/ directory.
        Executed at agent setup time, not per request.
        
        Args:
            agent_instance: The BookFinderAgent instance
            
        Returns:
            Dictionary mapping query names to SQL template strings
        """
        try:
            queries = {}
            queries_dir = os.path.join(
                os.path.dirname(__file__), "queries"
            )
            
            if not os.path.exists(queries_dir):
                logging.warning(f"Queries directory not found at {queries_dir}")
                return queries
            
            # Load all .sql files from queries directory
            for filename in os.listdir(queries_dir):
                if filename.endswith(".sql"):
                    query_name = filename[:-4]  # Remove .sql extension
                    filepath = os.path.join(queries_dir, filename)
                    with open(filepath, "r") as f:
                        queries[query_name] = f.read().strip()
                    logging.info(f"Loaded query template: {query_name}")
            
            logging.info(f"Successfully loaded {len(queries)} SQL templates")
            return queries
        except Exception as e:
            logging.error(f"Error loading SQL queries: {e}", exc_info=True)
            return {}

    @staticmethod
    def create_session_context_table(
        agent_instance,
        next_trace=None,
        trace=None,
    ) -> bool:
        """
        Create the session context table if it does not exist.
        Idempotent operation.
        
        Args:
            agent_instance: The BookFinderAgent instance
            next_trace: Optional trace handler
            trace: Optional trace handler
            
        Returns:
            True if table creation succeeded or table already exists, False otherwise
        """
        try:
            table_name = agent_instance.config.context_table
            create_query = agent_instance.queries.get("create_session_context_table", "")
            
            if not create_query:
                logging.warning(
                    f"No query template found for create_session_context_table. "
                    f"Skipping table creation."
                )
                return True
            
            # Format the query with the actual table name
            create_query = create_query.format(table_name=table_name)
            
            # Execute the CREATE TABLE IF NOT EXISTS query
            DatabaseRetrievalUtils._execute_query(
                agent_instance,
                query=create_query,
                params={},
                skip_stream_message_reset=True,
                next_trace=next_trace,
                trace=trace,
            )
            
            logging.info(f"Session context table '{table_name}' is ready")
            return True
        except Exception as e:
            logging.error(
                f"Error creating session context table: {e}",
                exc_info=True
            )
            return False

    @staticmethod
    def execute_vector_search(
        agent_instance,
        user_query: str,
        query_embedding: List[float],
        active_filters: Dict[str, Any],
        next_trace=None,
        trace=None,
    ) -> Tuple[List[str], Dict[str, Dict]]:
        """
        Execute parallel vector similarity searches across multiple tables.
        Returns deduplicated ISBN list and filter intersection data.
        
        Args:
            agent_instance: The BookFinderAgent instance
            user_query: The user's natural language query
            query_embedding: Vector embedding of the query (VECTOR(1536))
            active_filters: Dictionary of active filters {BookFinderFilterType: value}
            next_trace: Optional trace handler
            trace: Optional trace handler
            
        Returns:
            Tuple of (deduplicated_isbn_list, filter_intersection_data)
        """
        try:
            dedup_isbn_map = OrderedDict()  # Preserves insertion order and rank
            filter_intersection_map = {}
            
            if not active_filters:
                logging.warning("No active filters provided for vector search")
                return [], {}
            
            # Calculate dynamic ids_per_filter
            active_filter_count = len(active_filters)
            ids_per_filter = max(
                1,
                min(
                    -(-agent_instance.config.max_book_ids // active_filter_count),  # Ceiling division
                    15
                )
            )
            logging.info(
                f"Calculated ids_per_filter: {ids_per_filter} "
                f"(max_book_ids={agent_instance.config.max_book_ids}, "
                f"active_filters={active_filter_count})"
            )
            
            # Execute vector search for each active filter
            for filter_type, filter_value in active_filters.items():
                if not filter_value:
                    continue
                
                try:
                    filter_type_enum = BookFinderFilterType(filter_type)
                    filter_details = FILTER_TABLE_MAPPING.get(filter_type_enum)
                    
                    if not filter_details:
                        logging.warning(
                            f"No filter details found for {filter_type}. Skipping."
                        )
                        continue
                    
                    # Build the vector search query
                    table_name = filter_details.table
                    search_column = filter_details.search_column
                    return_column = filter_details.return_column
                    select_columns = ", ".join(filter_details.select_columns)
                    
                    similarity_threshold = (
                        filter_details.similarity_threshold
                        or agent_instance.config.similarity_threshold
                    )
                    
                    query_template = agent_instance.queries.get(
                        "retrieve_book_vector_search", ""
                    )
                    
                    if not query_template:
                        logging.warning(
                            "No query template found for retrieve_book_vector_search"
                        )
                        continue
                    
                    # Format query with actual values
                    vector_search_query = query_template.format(
                        select_columns=select_columns,
                        table_name=table_name,
                        search_column=search_column,
                        return_column=return_column,
                        limit=ids_per_filter,
                    )
                    
                    # Execute the vector search
                    results = DatabaseRetrievalUtils._execute_query(
                        agent_instance,
                        query=vector_search_query,
                        params=(
                            query_embedding,
                            1.0 - similarity_threshold,  # Convert threshold to distance
                            ids_per_filter,
                        ),
                        next_trace=next_trace,
                        trace=trace,
                    )
                    
                    # Track ISBNs and their scores
                    filter_isbns = []
                    for result in results:
                        isbn = result.get("isbn") or result.get(return_column)
                        if isbn:
                            filter_isbns.append(isbn)
                            # Use first occurrence (best rank) for deduplication
                            if isbn not in dedup_isbn_map:
                                dedup_isbn_map[isbn] = {
                                    "similarity_score": result.get(
                                        "similarity_score", 0.0
                                    ),
                                    "first_filter": filter_type,
                                }
                    
                    filter_intersection_map[filter_type] = filter_isbns
                    logging.info(
                        f"Filter '{filter_type}' returned {len(filter_isbns)} ISBNs"
                    )
                    
                except ValueError as ve:
                    logging.warning(f"Invalid filter type '{filter_type}': {ve}")
                    continue
                except Exception as fe:
                    logging.error(
                        f"Error processing filter '{filter_type}': {fe}",
                        exc_info=True,
                    )
                    continue
            
            deduplicated_isbns = list(dedup_isbn_map.keys())
            logging.info(
                f"Deduplicated vector search results: {len(deduplicated_isbns)} unique ISBNs "
                f"from {active_filter_count} filters"
            )
            
            return deduplicated_isbns, filter_intersection_map
        except Exception as e:
            logging.error(
                f"Error in execute_vector_search: {e}",
                exc_info=True,
            )
            return [], {}

    @staticmethod
    def retrieve_chunks(
        agent_instance,
        isbn_list: List[str],
        query_embedding: List[float],
        next_trace=None,
        trace=None,
    ) -> Dict[str, List[Dict]]:
        """
        Retrieve supporting manuscript chunks for each ISBN.
        
        Args:
            agent_instance: The BookFinderAgent instance
            isbn_list: List of ISBNs to retrieve chunks for
            query_embedding: Vector embedding of the query
            next_trace: Optional trace handler
            trace: Optional trace handler
            
        Returns:
            Dictionary mapping ISBN to list of chunks
        """
        try:
            chunks_by_isbn = {}
            
            if not isbn_list:
                return chunks_by_isbn
            
            query_template = agent_instance.queries.get("retrieve_book_chunks", "")
            
            if not query_template:
                logging.warning("No query template found for retrieve_book_chunks")
                return chunks_by_isbn
            
            # Execute chunk retrieval for all ISBNs
            # Using a single query with IN clause for efficiency
            chunk_table = FILTER_TABLE_MAPPING[
                BookFinderFilterType.SUPPORTING_CHUNK_DETAILS
            ].table
            
            max_chunks = agent_instance.config.max_chunks_to_use
            
            # Create placeholder list for IN clause
            isbn_placeholders = ", ".join(["%s"] * len(isbn_list))
            
            retrieve_chunks_query = query_template.format(
                chunk_table=chunk_table,
                isbn_placeholders=isbn_placeholders,
                limit=max_chunks,
            )
            
            results = DatabaseRetrievalUtils._execute_query(
                agent_instance,
                query=retrieve_chunks_query,
                params=tuple([query_embedding] + isbn_list + [max_chunks]),
                next_trace=next_trace,
                trace=trace,
            )
            
            # Group chunks by ISBN
            for result in results:
                isbn = result.get("isbn")
                if isbn:
                    if isbn not in chunks_by_isbn:
                        chunks_by_isbn[isbn] = []
                    chunks_by_isbn[isbn].append(result)
            
            logging.info(
                f"Retrieved chunks for {len(chunks_by_isbn)} ISBNs "
                f"(total chunks: {sum(len(c) for c in chunks_by_isbn.values())})"
            )
            return chunks_by_isbn
        except Exception as e:
            logging.error(
                f"Error in retrieve_chunks: {e}",
                exc_info=True,
            )
            return {}

    @staticmethod
    def insert_retrieved_documents(
        agent_instance,
        session_id: str,
        question: str,
        documents: List[Dict],
        next_trace=None,
        trace=None,
    ) -> Dict[str, str]:
        """
        Insert retrieved documents into the session context table.
        
        Args:
            agent_instance: The BookFinderAgent instance
            session_id: The session identifier
            question: The user query
            documents: List of document dictionaries with ISBN, score, chunks
            next_trace: Optional trace handler
            trace: Optional trace handler
            
        Returns:
            Dictionary mapping ISBN to context table row ID
        """
        try:
            if not documents:
                return {}
            
            context_table = agent_instance.config.context_table
            insert_query = agent_instance.queries.get("insert_retrieved_documents", "")
            
            if not insert_query:
                logging.warning(
                    "No query template found for insert_retrieved_documents"
                )
                return {}
            
            # Prepare batch insert params
            params_list = []
            for doc in documents:
                isbn = doc.get("isbn")
                context_score = doc.get("similarity_score", 0.0)
                chunk_ids = doc.get("chunk_ids", [])
                
                params_list.extend([
                    session_id,
                    isbn,
                    context_score,
                    False,  # is_displayed
                    False,  # is_expired
                    0,      # display_count
                    str(chunk_ids),  # chunk_ids as JSON
                ])
            
            # Build VALUES clause with placeholders
            values_clause = ", ".join(
                ["(%s, %s, %s, %s, %s, %s, %s)"] * len(documents)
            )
            
            insert_query = insert_query.format(
                context_table=context_table,
                values_clause=values_clause,
            )
            
            DatabaseRetrievalUtils._execute_query(
                agent_instance,
                query=insert_query,
                params=tuple(params_list),
                commit=True,
                next_trace=next_trace,
                trace=trace,
            )
            
            logging.info(
                f"Inserted {len(documents)} documents into session context table"
            )
            
            # Return mapping of ISBN to row ID (for pagination)
            return {doc.get("isbn"): doc.get("id") for doc in documents if doc.get("id")}
        except Exception as e:
            logging.error(
                f"Error in insert_retrieved_documents: {e}",
                exc_info=True,
            )
            return {}

    @staticmethod
    def fetch_show_more_books(
        agent_instance,
        session_id: str,
        question: str,
        show_more_length: int,
        next_trace=None,
        trace=None,
    ) -> List[Dict]:
        """
        Fetch undisplayed books for pagination (show more).
        
        Args:
            agent_instance: The BookFinderAgent instance
            session_id: The session identifier
            question: The original user query
            show_more_length: Number of additional books to fetch
            next_trace: Optional trace handler
            trace: Optional trace handler
            
        Returns:
            List of book dictionaries with context and chunks
        """
        try:
            context_table = agent_instance.config.context_table
            max_show_more = agent_instance.config.max_show_more_books
            
            fetch_query = agent_instance.queries.get("fetch_show_more_books", "")
            
            if not fetch_query:
                logging.warning("No query template found for fetch_show_more_books")
                return []
            
            fetch_query = fetch_query.format(
                context_table=context_table,
            )
            
            params = (
                session_id,
                question,
                show_more_length,
                max_show_more,
            )
            
            results = DatabaseRetrievalUtils._execute_query(
                agent_instance,
                query=fetch_query,
                params=params,
                next_trace=next_trace,
                trace=trace,
            )
            
            logging.info(
                f"Fetched {len(results)} additional books for show_more request"
            )
            return results
        except Exception as e:
            logging.error(
                f"Error in fetch_show_more_books: {e}",
                exc_info=True,
            )
            return []

    @staticmethod
    def mark_books_as_displayed(
        agent_instance,
        session_id: str,
        isbn_list: List[str],
        question: str,
        next_trace=None,
        trace=None,
    ) -> bool:
        """
        Mark books as displayed and increment display count.
        
        Args:
            agent_instance: The BookFinderAgent instance
            session_id: The session identifier
            isbn_list: List of ISBNs to mark as displayed
            question: The user query
            next_trace: Optional trace handler
            trace: Optional trace handler
            
        Returns:
            True if update succeeded, False otherwise
        """
        try:
            if not isbn_list:
                return True
            
            context_table = agent_instance.config.context_table
            update_query = agent_instance.queries.get("mark_books_as_displayed", "")
            
            if not update_query:
                logging.warning("No query template found for mark_books_as_displayed")
                return False
            
            # Build VALUES clause for multi-row update
            value_clauses = ", ".join(["(%s, %s)"] * len(isbn_list))
            
            update_query = update_query.format(
                context_table=context_table,
                value_clauses=value_clauses,
            )
            
            params = []
            for isbn in isbn_list:
                params.extend([isbn, 1])  # 1 for display_count increment
            params.extend([session_id, question])
            
            DatabaseRetrievalUtils._execute_query(
                agent_instance,
                query=update_query,
                params=tuple(params),
                commit=True,
                next_trace=next_trace,
                trace=trace,
            )
            
            logging.info(f"Marked {len(isbn_list)} books as displayed")
            return True
        except Exception as e:
            logging.error(
                f"Error in mark_books_as_displayed: {e}",
                exc_info=True,
            )
            return False

    @staticmethod
    def expire_old_context(
        agent_instance,
        session_id: str,
        next_trace=None,
        trace=None,
    ) -> bool:
        """
        Mark old session context as expired before a new search.
        Idempotent operation.
        
        Args:
            agent_instance: The BookFinderAgent instance
            session_id: The session identifier
            next_trace: Optional trace handler
            trace: Optional trace handler
            
        Returns:
            True if operation succeeded, False otherwise
        """
        try:
            context_table = agent_instance.config.context_table
            expire_query = agent_instance.queries.get("expire_old_context", "")
            
            if not expire_query:
                logging.warning("No query template found for expire_old_context")
                return True  # Not fatal if expiration fails
            
            expire_query = expire_query.format(context_table=context_table)
            
            DatabaseRetrievalUtils._execute_query(
                agent_instance,
                query=expire_query,
                params=(session_id,),
                commit=True,
                next_trace=next_trace,
                trace=trace,
            )
            
            logging.info(f"Expired old context for session {session_id}")
            return True
        except Exception as e:
            logging.error(
                f"Error in expire_old_context: {e}",
                exc_info=True,
            )
            return True  # Non-fatal

    @staticmethod
    def _execute_query(
        agent_instance,
        query: str,
        params: tuple = None,
        commit: bool = False,
        skip_stream_message_reset: bool = False,
        next_trace=None,
        trace=None,
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query with error handling and trace support.
        
        Args:
            agent_instance: The BookFinderAgent instance
            query: SQL query string
            params: Query parameters tuple
            commit: Whether to commit the transaction
            skip_stream_message_reset: Skip resetting streaming messages
            next_trace: Optional trace handler
            trace: Optional trace handler
            
        Returns:
            List of result dictionaries or empty list on error
        """
        try:
            if not params:
                params = {}
            
            # Configure SQL executor
            agent_instance.sql_executor_tool.sql_integration.config.is_commit = commit
            
            # Execute query
            result = agent_instance.sql_executor_tool.run(
                sql_query=query,
                params=params,
                next_trace=next_trace,
                trace=trace,
            )
            
            return result if isinstance(result, list) else []
        except Exception as exc:
            logging.error(
                f"SQL execution failed: {exc}",
                exc_info=True,
            )
            return []

