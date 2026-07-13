import logging
import os
import traceback
from typing import Any, Dict, List, Optional, Tuple

try:
    import psycopg2
    import psycopg2.errors
except ImportError:
    # Handle case where psycopg2 is not installed directly
    psycopg2 = None

from agents.book_finder_agent.book_finder_filters import (
    BookFilterType,
    FILTER_TABLE_MAPPING,
    NORMALIZED_TABLE_MAPPING,
    FilterDetails,
    JoinDefinition,
)


class ConfigurationError(Exception):
    """Raised when configuration validation fails during startup."""
    pass


class DatabaseConnectionError(Exception):
    """Raised when database connection fails (psycopg2.OperationalError)."""
    pass


class DatabaseRetrievalUtils:
    """
    Database retrieval and query-template helpers for BookFinderAgent.
    Provides static methods for parameterized SQL execution, dynamic join path
    construction, and SQL template loading.
    """

    @staticmethod
    def _execute_query(
        agent,
        query: str,
        params: Tuple = (),
        commit: bool = False,
        filter_type: str = None,
        user_role: Optional[str] = None,
        trace: Optional[dict] = None,
        next_trace: Optional[dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a parameterized SQL query via SQLExecutorTool with error handling and timeout policies.
        
        Implements tiered timeout enforcement based on user role and comprehensive error handling
        for database connection failures, query execution failures, and timeouts.
        
        Args:
            agent: The BookFinderAgent instance (must have sql_executor_tool)
            query: SQL query string with %s placeholders
            params: Tuple of parameters to bind to the query
            commit: If True, commit the transaction after execution
            filter_type: Optional filter type for logging/tracing
            user_role: Optional user role ('admin', 'report', or standard user) for timeout determination
            trace: Current execution trace dict (used for correlation ID logging)
            next_trace: Trace for downstream tool calls
            
        Returns:
            List[Dict[str, Any]]: List of result row dicts, or empty list on query execution error.
            
        Raises:
            DatabaseConnectionError: If psycopg2.OperationalError occurs (connection failure).
        """
        try:
            # Extract correlation ID from trace for request traceability
            correlation_id = None
            if trace and isinstance(trace, dict):
                correlation_id = trace.get('root', {}).get('correlation_id') if isinstance(trace.get('root'), dict) else trace.get('correlation_id')
            
            # Determine timeout window based on user role (ACT-7 requirement)
            query_timeout = 300 if user_role in ['admin', 'report'] else 30
            timeout_label = f"{query_timeout}s (admin/report role)" if user_role in ['admin', 'report'] else f"{query_timeout}s (standard user)"
            
            # Prepare parameters: ensure it's a tuple
            if params is None:
                params = ()
            elif not isinstance(params, tuple):
                params = tuple(params) if isinstance(params, (list, set)) else (params,)
            
            # Log query execution with correlation ID and timeout
            correlation_str = f" [correlation_id={correlation_id}]" if correlation_id else ""
            logging.info(
                f"[DB_EXECUTE] Starting query execution (filter_type={filter_type}, timeout={timeout_label}){correlation_str}. "
                f"Query: {query[:150]}... | Params: {len(params)} placeholders"
            )
            
            # Apply timeout to SQL executor tool configuration
            if hasattr(agent, 'sql_executor_tool') and hasattr(agent.sql_executor_tool, 'config'):
                agent.sql_executor_tool.config.query_timeout = query_timeout
            
            # Set commit flag on SQL executor integration if available
            if hasattr(agent, 'sql_executor_tool') and hasattr(agent.sql_executor_tool, 'sql_integration'):
                agent.sql_executor_tool.sql_integration.config.is_commit = commit
            
            # Execute query via SQLExecutorTool
            result = agent.sql_executor_tool.run(
                sql_query=query,
                params=params,
                next_trace=next_trace,
                trace=trace,
            )
            
            # Normalize result to list of dicts
            if isinstance(result, list):
                # Already a list, ensure all items are dicts
                normalized = []
                for row in result:
                    if isinstance(row, dict):
                        normalized.append(row)
                    elif hasattr(row, '_asdict'):  # namedtuple
                        normalized.append(row._asdict())
                    else:
                        logging.warning(f"[DB_EXECUTE] Could not normalize row type {type(row)}{correlation_str}")
                
                # Log successful execution
                logging.info(
                    f"[DB_EXECUTE] Query completed successfully (filter_type={filter_type}){correlation_str}. "
                    f"Returned {len(normalized)} rows."
                )
                return normalized
            else:
                logging.warning(
                    f"[DB_EXECUTE] Unexpected result type from sql_executor_tool: {type(result)}{correlation_str}"
                )
                return []
                
        except Exception as exc:
            # Extract correlation ID for error logging
            correlation_id = None
            if trace and isinstance(trace, dict):
                correlation_id = trace.get('root', {}).get('correlation_id') if isinstance(trace.get('root'), dict) else trace.get('correlation_id')
            correlation_str = f" [correlation_id={correlation_id}]" if correlation_id else ""
            
            # Detect and handle psycopg2 exceptions
            exc_type = type(exc).__name__
            
            # Check for QueryCanceled (timeout) error
            if psycopg2 and hasattr(psycopg2, 'errors'):
                try:
                    if isinstance(exc, psycopg2.errors.QueryCanceled):
                        logging.error(
                            f"[DB_EXECUTE] Query timeout exceeded (filter_type={filter_type}){correlation_str}. "
                            f"Timeout: {query_timeout}s. Query: {query[:150]}..."
                        )
                        return []
                except (AttributeError, TypeError):
                    pass
            
            # Check for OperationalError (connection failures)
            if psycopg2 and isinstance(exc, psycopg2.OperationalError):
                logging.critical(
                    f"[DB_EXECUTE] Database connection failed (filter_type={filter_type}){correlation_str}. "
                    f"Error: {str(exc)}. Raising DatabaseConnectionError.",
                    exc_info=True
                )
                raise DatabaseConnectionError(
                    f"Failed to connect to database: {str(exc)}"
                )
            
            # Check for DatabaseError (all database-level errors)
            if psycopg2 and isinstance(exc, psycopg2.DatabaseError):
                logging.error(
                    f"[DB_EXECUTE] Database query failed (filter_type={filter_type}){correlation_str}. "
                    f"Error type: {exc_type}. Query: {query[:150]}... | Params: {params}. "
                    f"Error message: {str(exc)}",
                    exc_info=True
                )
                return []
            
            # Generic exception handler (non-psycopg2 errors)
            logging.error(
                f"[DB_EXECUTE] Unexpected error during query execution (filter_type={filter_type}){correlation_str}. "
                f"Error type: {exc_type}. Query: {query[:150]}... | Error: {str(exc)}",
                exc_info=True
            )
            return []

    @staticmethod
    def _build_join_paths(
        agent,
        target_table: str,
        target_filter_enum: BookFilterType,
    ) -> List[Dict]:
        """
        Build join paths from books table to target table for hybrid searches.
        
        Determines the sequence of SQL JOINs required to fetch data from the
        target table based on the filter type and table relationships defined
        in FILTER_TABLE_MAPPING and NORMALIZED_TABLE_MAPPING.
        
        Args:
            agent: The BookFinderAgent instance
            target_table: Target table name (e.g., 'authors', 'genres')
            target_filter_enum: BookFilterType enum identifying the filter
            
        Returns:
            List[Dict]: List of join definitions with keys:
                - "from_table": Source table
                - "to_table": Target table
                - "join_column_left": Column in source table
                - "join_column_right": Column in target table
                - "join_type": "INNER" or "LEFT OUTER"
                
                Returns empty list if target_table is the books table (no join needed)
        """
        try:
            table_joins = []
            BASE_TABLE = "books"
            
            # If target is already the books table, no join needed
            if target_table == BASE_TABLE:
                return []
            
            # Get filter details from mapping
            if target_filter_enum not in FILTER_TABLE_MAPPING:
                logging.warning(
                    f"Filter type {target_filter_enum} not found in FILTER_TABLE_MAPPING"
                )
                return []
            
            filter_details = FILTER_TABLE_MAPPING[target_filter_enum]
            
            # Path A: Many-to-many with normalized mapping (e.g., authors, genres)
            # These tables have a junction table pattern
            if target_table in ["authors", "genres", "contributors", "locations", "publishers"]:
                # Direct join: books -> target_table (book_id foreign key)
                table_joins.append({
                    "from_table": BASE_TABLE,
                    "to_table": target_table,
                    "join_column_left": "book_id",
                    "join_column_right": "book_id",
                    "join_type": "LEFT OUTER"
                })
            
            # Path B: Normalized junction tables (many-to-many relationships)
            elif target_table in NORMALIZED_TABLE_MAPPING:
                join_def = NORMALIZED_TABLE_MAPPING[target_table]
                
                # Join 1: books -> intermediate table
                table_joins.append({
                    "from_table": BASE_TABLE,
                    "to_table": join_def.to_table,
                    "join_column_left": "book_id",
                    "join_column_right": "book_id",
                    "join_type": "LEFT OUTER"
                })
            
            # Path C: Standard case (direct foreign key to books)
            else:
                table_joins.append({
                    "from_table": BASE_TABLE,
                    "to_table": target_table,
                    "join_column_left": "book_id",
                    "join_column_right": "book_id",
                    "join_type": "LEFT OUTER"
                })
            
            logging.info(f"Built {len(table_joins)} join paths for {target_table}")
            return table_joins
            
        except Exception as exc:
            logging.error(
                f"Error building join paths for {target_table}: {exc}",
                exc_info=True
            )
            return []

    @staticmethod
    def _fetch_organization_ids(
        agent,
        organization_names: List[str],
        trace: Optional[dict] = None,
        next_trace: Optional[dict] = None,
    ) -> List[str]:
        """
        Fetch organization IDs from the database by name.
        
        Executes a SELECT query against the organizations table using
        PostgreSQL's = ANY() operator for bulk name matching.
        
        Args:
            agent: The BookFinderAgent instance
            organization_names: List of organization names to search for
            trace: Current execution trace
            next_trace: Trace for downstream tool calls
            
        Returns:
            List[str]: List of UUID strings for matched organizations,
                      or empty list if no matches or error
        """
        try:
            if not organization_names or len(organization_names) == 0:
                return []
            
            # Construct parameterized query
            query = (
                "SELECT org_id FROM organizations "
                "WHERE org_name = ANY(%s) "
                "ORDER BY org_name ASC"
            )
            
            # Execute query
            query_result = DatabaseRetrievalUtils._execute_query(
                agent=agent,
                query=query,
                params=(tuple(organization_names),),
                trace=trace,
                next_trace=next_trace,
            )
            
            # Extract organization IDs
            organization_ids = []
            for row in query_result:
                org_id = row.get("org_id")
                if org_id:
                    organization_ids.append(str(org_id))
            
            logging.info(
                f"Found {len(organization_ids)} organizations out of "
                f"{len(organization_names)} requested"
            )
            
            return organization_ids
            
        except Exception as exc:
            logging.error(
                f"Error fetching organization IDs: {exc}",
                exc_info=True
            )
            return []

    @staticmethod
    def _read_queries(agent) -> Dict[str, str]:
        """
        Load SQL query templates from the queries/ directory.
        
        Reads all .sql files from the agent package's queries/ subdirectory
        and validates that all mandatory templates are present. Strictly rejects
        startup if any required template is missing.
        
        Args:
            agent: The BookFinderAgent instance
            
        Returns:
            Dict[str, str]: Dictionary with query names (filenames without .sql)
                           as keys and SQL content as values
                           
        Raises:
            ConfigurationError: If any mandatory template is missing
        """
        try:
            # Define mandatory SQL templates
            REQUIRED_TEMPLATES = [
                "create_chat_data_table",
                "retrieve_books_semantic",
                "retrieve_books_exact_match",
                "fetch_show_more_docs",
                "fallback_fetch_show_more_docs",
                "fetch_latest_question_for_session",
                "fetch_filtered_question_documents",
                "insert_retrieved_documents",
                "upsert_retrieved_documents",
                "mark_books_as_displayed",
                "retrieve_session_context",
                "expire_old_sessions",
            ]
            
            # Resolve queries directory relative to agent module
            agent_module_dir = os.path.dirname(__file__)
            queries_dir = os.path.join(agent_module_dir, "queries")
            
            if not os.path.exists(queries_dir):
                raise ConfigurationError(
                    f"Queries directory not found at {queries_dir}"
                )
            
            # Load all .sql files
            query_dictionary = {}
            
            for filename in os.listdir(queries_dir):
                if filename.endswith(".sql"):
                    query_name = filename[:-4]  # Remove .sql extension
                    query_path = os.path.join(queries_dir, filename)
                    
                    try:
                        with open(query_path, "r") as f:
                            query_content = f.read().strip()
                        
                        if query_content:
                            query_dictionary[query_name] = query_content
                        else:
                            logging.warning(
                                f"SQL file {filename} is empty"
                            )
                    except Exception as e:
                        logging.error(
                            f"Error reading SQL file {filename}: {e}"
                        )
            
            # Validate all mandatory templates are present
            missing_templates = [
                t for t in REQUIRED_TEMPLATES if t not in query_dictionary
            ]
            
            if missing_templates:
                raise ConfigurationError(
                    f"Missing mandatory SQL templates: {missing_templates}. "
                    f"Found: {list(query_dictionary.keys())}"
                )
            
            logging.info(
                f"Successfully loaded {len(query_dictionary)} SQL templates "
                f"from {queries_dir}"
            )
            
            return query_dictionary
            
        except ConfigurationError as exc:
            # Strictly reject startup on configuration errors
            logging.critical(
                f"Configuration error in _read_queries: {exc}"
            )
            raise
        except Exception as exc:
            logging.error(
                f"Unexpected error reading queries: {exc}",
                exc_info=True
            )
            raise ConfigurationError(
                f"Failed to load SQL templates: {exc}"
            )

