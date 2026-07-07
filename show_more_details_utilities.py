import json
import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class ShowMoreDetailsUtils:
    """Session state and pagination utilities for BookFinderAgent show-more functionality."""

    def fetch_session_context(
        self,
        session_id: str,
        trace=None,
        next_trace=None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch previously cached execution context for a session.
        Used for pagination and show-more requests.
        
        Args:
            session_id (str): The session ID to fetch context for
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            dict: Cached session context or None if not found
        """
        try:
            query = f"""
                SELECT context_data, retrieved_documents, created_at 
                FROM {self.config.context_table}
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            result = self._execute_query(
                query=query,
                params=(session_id,),
                trace=trace,
                next_trace=next_trace
            )
            
            if result and len(result) > 0:
                context_row = result[0]
                context_data = context_row.get("context_data", {})
                
                if isinstance(context_data, str):
                    context_data = json.loads(context_data)
                
                logging.info(f"Fetched session context for session {session_id}")
                return context_data
            
            logging.info(f"No session context found for session {session_id}")
            return None
            
        except Exception as e:
            logging.error(f"Error fetching session context: {e}", exc_info=True)
            return None


    def fetch_undisplayed_books(
        self,
        session_id: str,
        limit: int,
        trace=None,
        next_trace=None
    ) -> List[Dict[str, Any]]:
        """
        Fetch previously retrieved but not-yet-displayed books for pagination.
        
        Args:
            session_id (str): The session ID to fetch books for
            limit (int): Maximum number of books to fetch
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            list: List of undisplayed book documents
        """
        try:
            query = f"""
                SELECT book_id, book_data, similarity_score 
                FROM {self.config.context_table}
                WHERE session_id = %s AND is_displayed = FALSE
                ORDER BY similarity_score DESC
                LIMIT %s
            """
            
            result = self._execute_query(
                query=query,
                params=(session_id, limit),
                trace=trace,
                next_trace=next_trace
            )
            
            books = []
            for row in result:
                book_data = row.get("book_data", {})
                if isinstance(book_data, str):
                    book_data = json.loads(book_data)
                
                book_id = row.get("book_id")
                books.append({book_id: book_data})
            
            logging.info(f"Fetched {len(books)} undisplayed books for session {session_id}")
            return books
            
        except Exception as e:
            logging.error(f"Error fetching undisplayed books: {e}", exc_info=True)
            return []


    def mark_books_as_displayed(
        self,
        session_id: str,
        book_ids: List[str],
        trace=None,
        next_trace=None
    ) -> bool:
        """
        Mark retrieved books as displayed in session context.
        
        Args:
            session_id (str): The session ID
            book_ids (List[str]): List of book IDs to mark as displayed
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not book_ids:
                return True
            
            query = f"""
                UPDATE {self.config.context_table}
                SET is_displayed = TRUE
                WHERE session_id = %s AND book_id IN %s
            """
            
            self._execute_query(
                query=query,
                params=(session_id, tuple(book_ids)),
                commit=True,
                trace=trace,
                next_trace=next_trace
            )
            
            logging.info(f"Marked {len(book_ids)} books as displayed for session {session_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error marking books as displayed: {e}", exc_info=True)
            return False


    def insert_retrieved_documents(
        self,
        session_id: str,
        question: str,
        retrieved_documents: List[Dict[str, Any]],
        trace=None,
        next_trace=None
    ) -> bool:
        """
        Insert newly retrieved documents into session context table.
        
        Args:
            session_id (str): The session ID
            question (str): The original user question
            retrieved_documents (List[Dict]): Documents to store
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            query = f"""
                INSERT INTO {self.config.context_table}
                (session_id, question, book_id, book_data, is_displayed, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            now = datetime.utcnow()
            
            for doc in retrieved_documents:
                book_id = next(iter(doc.keys()))
                book_data = doc.get(book_id, {})
                
                self._execute_query(
                    query=query,
                    params=(
                        session_id,
                        question,
                        book_id,
                        json.dumps(book_data),
                        False,
                        now
                    ),
                    commit=True,
                    trace=trace,
                    next_trace=next_trace
                )
            
            logging.info(f"Inserted {len(retrieved_documents)} documents into session {session_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error inserting retrieved documents: {e}", exc_info=True)
            return False


    def fetch_latest_question(
        self,
        session_id: str,
        trace=None,
        next_trace=None
    ) -> Optional[str]:
        """
        Fetch the most recent question asked in a session.
        
        Args:
            session_id (str): The session ID
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            str: The latest question or None if not found
        """
        try:
            query = f"""
                SELECT question 
                FROM {self.config.context_table}
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            result = self._execute_query(
                query=query,
                params=(session_id,),
                trace=trace,
                next_trace=next_trace
            )
            
            if result and len(result) > 0:
                question = result[0].get("question")
                logging.info(f"Fetched latest question for session {session_id}")
                return question
            
            return None
            
        except Exception as e:
            logging.error(f"Error fetching latest question: {e}", exc_info=True)
            return None


    def fetch_filtered_documents(
        self,
        session_id: str,
        filters: Dict[str, Any],
        limit: int = 10,
        trace=None,
        next_trace=None
    ) -> List[Dict[str, Any]]:
        """
        Fetch session documents filtered by JSONB metadata.
        Used for applying new filters to existing session context.
        
        Args:
            session_id (str): The session ID
            filters (Dict): JSONB filters to apply
            limit (int): Maximum number of documents to return
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            list: Filtered list of book documents
        """
        try:
            # Build JSONB filter conditions
            where_conditions = ["session_id = %s"]
            params = [session_id]
            
            for key, value in filters.items():
                where_conditions.append(f"book_data->'{key}' = %s")
                params.append(value)
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT book_id, book_data 
                FROM {self.config.context_table}
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s
            """
            
            params.append(limit)
            
            result = self._execute_query(
                query=query,
                params=tuple(params),
                trace=trace,
                next_trace=next_trace
            )
            
            books = []
            for row in result:
                book_data = row.get("book_data", {})
                if isinstance(book_data, str):
                    book_data = json.loads(book_data)
                
                book_id = row.get("book_id")
                books.append({book_id: book_data})
            
            logging.info(f"Fetched {len(books)} filtered documents for session {session_id}")
            return books
            
        except Exception as e:
            logging.error(f"Error fetching filtered documents: {e}", exc_info=True)
            return []


    def cleanup_old_sessions(
        self,
        days_old: int = 30,
        trace=None,
        next_trace=None
    ) -> int:
        """
        Delete session context records older than specified days.
        Helps maintain database size and removes stale session data.
        
        Args:
            days_old (int): Delete sessions older than this many days
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            int: Number of records deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            query = f"""
                DELETE FROM {self.config.context_table}
                WHERE created_at < %s
            """
            
            self._execute_query(
                query=query,
                params=(cutoff_date,),
                commit=True,
                trace=trace,
                next_trace=next_trace
            )
            
            logging.info(f"Cleaned up session context records older than {days_old} days")
            return 1
            
        except Exception as e:
            logging.error(f"Error cleaning up old sessions: {e}", exc_info=True)
            return 0

