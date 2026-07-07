import logging
import traceback
import os
from typing import Any, Dict, List, Optional, Tuple

from book_helper import (
    BookFilterType,
    FILTER_TYPE_TO_TEXT_MAP,
    BOOK_FILTER_MAPPING,
    FilterDetails,
)


class DatabaseRetrievalUtils:
    """Database retrieval and query-template helpers for BookFinderAgent."""
    
    def fetch_publisher_ids(self, publisher_names, trace=None, next_trace=None):
        """
        Fetch Publisher IDs from database based on publisher names.
        
        Args:
            publisher_names (tuple): Tuple of publisher names to search for
            trace (dict): Trace dictionary for execution logging
            next_trace (dict): Next trace object for tool chaining
        
        Returns:
            list: List of publisher IDs matching the given names
        """
        try:
            if len(publisher_names) == 0:
                return []

            query = f"SELECT publisher_id FROM {self.organization_table} WHERE publisher_name IN %s"
            
            query_result = DatabaseRetrievalUtils._execute_query(
                self,
                query=query,
                params=(tuple(publisher_names),),
                trace=trace,
                next_trace=next_trace
            )

            publisher_ids = []
            for item in query_result:
                publisher_id = item.get("publisher_id", None)
                if publisher_id:
                    publisher_ids.append(publisher_id)

            logging.info(f"Publisher IDs fetched: {publisher_ids}")
            return publisher_ids
            
        except Exception as e:
            logging.error(f"Error fetching publisher IDs: {e}", exc_info=True)
            return []


    def _execute_query(
        self,
        query: str,
        params: tuple = None,
        commit: bool = False,
        filter_type: str = None,
        filter_value: str = None,
        mapping: Dict = None,
        skip_stream_message_reset: bool = False,
        next_trace=None,
        trace=None,
    ) -> List[Dict[str, Any]]:
        """Execute SQL query with error handling and streaming message management."""
        try:
            # Update SQL executor messages if filter metadata is provided
            if filter_type and filter_value and mapping:
                logging.info(f"Updating SQL executor messages for filter_type: {filter_type}, filter_value: {filter_value}")
                table_name = mapping.table
                select_columns = mapping.select_columns
                self.sql_executor_tool.config.stream_start_message = (
                    self.original_sql_start_header_messages
                    .replace("<table_name>", table_name)
                    .replace("<filter_type>", FILTER_TYPE_TO_TEXT_MAP.get(filter_type, filter_type))
                    .replace('<filter_value>', filter_value)
                )
                self.sql_executor_tool.config.stream_end_message = (
                    self.original_sql_end_header_messages
                    .replace("<table_name>", table_name)
                    .replace("<filter_type>", FILTER_TYPE_TO_TEXT_MAP.get(filter_type, filter_type))
                    .replace('<filter_value>', filter_value)
                )
                if select_columns and self.original_format_columns:
                    self.sql_executor_tool.config.format_result_columns = ", ".join(select_columns)
            else:
                if not skip_stream_message_reset:
                    self.sql_executor_tool.config.stream_start_message = ""
                    self.sql_executor_tool.config.stream_end_message = ""
            
            # Normalize params
            if not params:
                params = {}

            # Set commit flag on SQL integration
            self.sql_executor_tool.sql_integration.config.is_commit = commit
            
            # Execute query via SQL executor tool
            result = self.sql_executor_tool.run(
                sql_query=query,
                params=params,
                next_trace=next_trace,
                trace=trace,
            )

            # Restore original streaming messages
            self.sql_executor_tool.config.stream_start_message = (
                self.original_sql_start_header_messages
            )
            self.sql_executor_tool.config.stream_end_message = (
                self.original_sql_end_header_messages
            )
            
            return result if isinstance(result, list) else []
            
        except Exception as exc:
            logging.error(f"SQL execution failed: {exc}", exc_info=True)
            return []


    def _build_join_paths(
        self,
        target_table: str,
        target_filter_enum: BookFilterType,
        target_filter_config: FilterDetails,
        book_conf: FilterDetails,
        author_conf: FilterDetails,
        genre_conf: FilterDetails,
        excerpt_conf: FilterDetails,
    ) -> List[Dict]:
        """
        Build join paths based on target table and filter type.
        Returns list of join definitions with their column mappings.
        
        Args:
            target_table (str): The table being queried
            target_filter_enum (BookFilterType): The filter type enumeration
            target_filter_config (FilterDetails): Configuration for the target filter
            book_conf (FilterDetails): Configuration for book metadata table
            author_conf (FilterDetails): Configuration for author table
            genre_conf (FilterDetails): Configuration for genre table
            excerpt_conf (FilterDetails): Configuration for excerpt table
        
        Returns:
            list: List of join path definitions
        """
        table_joins = []
        BOOK_TABLE = book_conf.table
        AUTHOR_TABLE = author_conf.table
        AUTHOR_NORMALIZED_TABLE = author_conf.normalized_mapping.normalized_table if author_conf.normalized_mapping else None
        GENRE_TABLE = genre_conf.table
        EXCERPT_TABLE = excerpt_conf.table

        # Path A: Target is BOOK_METADATA table (no joins needed)
        if target_table == BOOK_TABLE:
            pass

        # Path B: Target is AUTHOR table (with normalized mapping)
        elif target_table == AUTHOR_TABLE and target_filter_config.normalized_mapping:
            author_norm_mapping = target_filter_config.normalized_mapping
            table_joins.append({
                "tables": (AUTHOR_TABLE, AUTHOR_NORMALIZED_TABLE),
                "columns": (author_norm_mapping.source_foreign_key, author_norm_mapping.normalized_foreign_key)
            })
            table_joins.append({
                "tables": (AUTHOR_NORMALIZED_TABLE, BOOK_TABLE),
                "columns": (author_norm_mapping.book_id_column, "book_id")
            })

        # Path C: Target is AUTHOR table (legacy - no normalized mapping)
        elif target_table == AUTHOR_TABLE:
            table_joins.append({
                "tables": (AUTHOR_TABLE, BOOK_TABLE),
                "columns": ("book_id", "book_id")
            })

        # Path D: Target is GENRE table
        elif target_table == GENRE_TABLE:
            table_joins.append({
                "tables": (GENRE_TABLE, BOOK_TABLE),
                "columns": ("book_id", "book_id")
            })

        # Path E: Target is EXCERPT table
        elif target_table == EXCERPT_TABLE:
            table_joins.append({
                "tables": (EXCERPT_TABLE, BOOK_TABLE),
                "columns": ("book_id", "book_id")
            })

        # Path F: Target has normalized mapping
        elif target_filter_config.normalized_mapping:
            norm_mapping = target_filter_config.normalized_mapping
            NORM_TABLE = norm_mapping.normalized_table
            table_joins.append({
                "tables": (target_table, NORM_TABLE),
                "columns": (norm_mapping.source_foreign_key, norm_mapping.normalized_foreign_key)
            })
            table_joins.append({
                "tables": (NORM_TABLE, BOOK_TABLE),
                "columns": (norm_mapping.book_id_column, "book_id")
            })

        # Path G: Standard case (target -> book)
        else:
            table_joins.append({
                "tables": (target_table, BOOK_TABLE),
                "columns": ("book_id", "book_id")
            })

        return table_joins


    @staticmethod
    def _read_queries(agent_instance) -> Dict[str, str]:
        """
        Read SQL query templates from the queries directory.
        
        Args:
            agent_instance: The agent instance to access its base path
        
        Returns:
            dict: Dictionary mapping query names to SQL template strings
        """
        queries = {}
        try:
            queries_dir = os.path.join(os.path.dirname(__file__), "queries")
            
            query_files = [
                "vector_query.sql",
                "filter_query_exact_match.sql",
                "vector_filter_query_with_join.sql",
                "create_chat_data_table.sql",
                "insert_retrieved_documents.sql",
                "upsert_retrieved_documents.sql",
                "fetch_show_more_docs.sql",
                "fallback_fetch_show_more_docs.sql",
                "fetch_latest_question_for_session.sql",
                "mark_books_as_displayed.sql",
                "retrieve_final_chunks.sql"
            ]
            
            for query_file in query_files:
                file_path = os.path.join(queries_dir, query_file)
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        query_name = query_file.replace(".sql", "")
                        queries[query_name] = f.read().strip()
                    logging.info(f"Loaded query template: {query_name}")
                else:
                    logging.warning(f"Query file not found: {file_path}")
            
            return queries
            
        except Exception as e:
            logging.error(f"Error reading query templates: {e}", exc_info=True)
            return {}

