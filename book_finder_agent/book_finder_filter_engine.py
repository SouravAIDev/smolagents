import logging
from typing import Any, Dict, Optional, Tuple

from book_finder_agent.book_finder_helpers import (
    BookFinderFilterType,
    FILTER_TABLE_MAPPING,
    FilterDetails,
)


class FilterEngine:
    """Utilities for dynamic filter configuration and query building."""

    @staticmethod
    def get_filter_details(filter_type: str) -> Optional[FilterDetails]:
        """
        Retrieve filter configuration details by filter type.
        
        Args:
            filter_type: String representation of BookFinderFilterType
            
        Returns:
            FilterDetails if found, None otherwise
        """
        try:
            filter_enum = BookFinderFilterType(filter_type)
            return FILTER_TABLE_MAPPING.get(filter_enum)
        except ValueError:
            logging.warning(f"Invalid filter type: {filter_type}")
            return None

    @staticmethod
    def validate_filter_type(filter_type: str) -> bool:
        """
        Validate that a filter type is a valid BookFinderFilterType.
        
        Args:
            filter_type: String to validate
            
        Returns:
            True if valid BookFinderFilterType, False otherwise
        """
        try:
            BookFinderFilterType(filter_type)
            return True
        except ValueError:
            return False

    @staticmethod
    def apply_filter_similarity_threshold(
        agent_instance,
        filter_type: str,
        fallback_threshold: Optional[float] = None,
    ) -> float:
        """
        Get the similarity threshold for a specific filter.
        Falls back to agent config if not defined at filter level.
        
        Args:
            agent_instance: The BookFinderAgent instance
            filter_type: The filter type identifier
            fallback_threshold: Default threshold if not found
            
        Returns:
            Similarity threshold between 0.0 and 1.0
        """
        try:
            filter_details = FilterEngine.get_filter_details(filter_type)
            
            if filter_details and filter_details.similarity_threshold is not None:
                return filter_details.similarity_threshold
            
            if hasattr(agent_instance, 'config') and hasattr(
                agent_instance.config, 'similarity_threshold'
            ):
                return agent_instance.config.similarity_threshold
            
            return fallback_threshold or 0.65
        except Exception as e:
            logging.warning(
                f"Error retrieving similarity threshold for {filter_type}: {e}"
            )
            return fallback_threshold or 0.65

    @staticmethod
    def apply_filter_similarity_threshold_hard(
        agent_instance,
        filter_type: str,
        fallback_threshold: Optional[float] = None,
    ) -> float:
        """
        Get the hard similarity threshold for a specific filter (for hard filters).
        Used when exact or near-exact matches are required.
        
        Args:
            agent_instance: The BookFinderAgent instance
            filter_type: The filter type identifier
            fallback_threshold: Default threshold if not found
            
        Returns:
            Similarity threshold between 0.0 and 1.0
        """
        try:
            filter_details = FilterEngine.get_filter_details(filter_type)
            
            if filter_details and filter_details.filter_similarity_threshold is not None:
                return filter_details.filter_similarity_threshold
            
            if hasattr(agent_instance, 'config') and hasattr(
                agent_instance.config, 'filter_similarity_threshold'
            ):
                return agent_instance.config.filter_similarity_threshold
            
            return fallback_threshold or 0.75
        except Exception as e:
            logging.warning(
                f"Error retrieving hard similarity threshold for {filter_type}: {e}"
            )
            return fallback_threshold or 0.75

    @staticmethod
    def get_filter_search_type(filter_type: str) -> str:
        """
        Get the search type for a filter (semantic_search, exact_match, etc.).
        
        Args:
            filter_type: The filter type identifier
            
        Returns:
            Search type string (e.g., 'semantic_search', 'exact_match')
        """
        filter_details = FilterEngine.get_filter_details(filter_type)
        if filter_details and filter_details.search_type:
            return filter_details.search_type
        return "semantic_search"

    @staticmethod
    def get_filter_mode(filter_type: str) -> str:
        """
        Get the filter mode (soft_filter or hard_filter).
        
        Args:
            filter_type: The filter type identifier
            
        Returns:
            Filter mode string ('soft_filter' or 'hard_filter')
        """
        filter_details = FilterEngine.get_filter_details(filter_type)
        if filter_details and filter_details.filter_mode:
            return filter_details.filter_mode
        return "soft_filter"

    @staticmethod
    def get_select_columns(filter_type: str) -> list:
        """
        Get the columns to select from the filter's table.
        
        Args:
            filter_type: The filter type identifier
            
        Returns:
            List of column names
        """
        filter_details = FilterEngine.get_filter_details(filter_type)
        if filter_details and filter_details.select_columns:
            return filter_details.select_columns
        return []

    @staticmethod
    def get_table_name(filter_type: str) -> Optional[str]:
        """
        Get the database table name for a filter.
        
        Args:
            filter_type: The filter type identifier
            
        Returns:
            Table name or None if not found
        """
        filter_details = FilterEngine.get_filter_details(filter_type)
        if filter_details:
            return filter_details.table
        return None

    @staticmethod
    def get_search_column(filter_type: str) -> Optional[str]:
        """
        Get the column used for semantic search in a filter.
        
        Args:
            filter_type: The filter type identifier
            
        Returns:
            Column name for vector search or None if not found
        """
        filter_details = FilterEngine.get_filter_details(filter_type)
        if filter_details:
            return filter_details.search_column
        return None

    @staticmethod
    def get_return_column(filter_type: str) -> Optional[str]:
        """
        Get the column that should be returned from a filter query.
        Typically the book identifier (isbn, book_id, etc.).
        
        Args:
            filter_type: The filter type identifier
            
        Returns:
            Column name for returned identifier or None if not found
        """
        filter_details = FilterEngine.get_filter_details(filter_type)
        if filter_details:
            return filter_details.return_column
        return None

    @staticmethod
    def get_primary_key(filter_type: str) -> Optional[str]:
        """
        Get the primary key column for a filter's table.
        
        Args:
            filter_type: The filter type identifier
            
        Returns:
            Primary key column name or None if not found
        """
        filter_details = FilterEngine.get_filter_details(filter_type)
        if filter_details:
            return filter_details.primary_key
        return None

    @staticmethod
    def normalize_filter_value(filter_type: str, value: Any) -> Any:
        """
        Normalize filter value for SQL parameterization.
        Converts specific data types as needed for the filter.
        
        Args:
            filter_type: The filter type identifier
            value: The filter value to normalize
            
        Returns:
            Normalized value suitable for SQL parameters
        """
        if value is None:
            return None
        
        search_type = FilterEngine.get_filter_search_type(filter_type)
        
        if search_type == "exact_match":
            return str(value).lower().strip()
        elif search_type == "date_search":
            # For date filters, value should already be in proper format
            return str(value)
        elif search_type == "semantic_search":
            return str(value).strip()
        else:
            return str(value).strip()

    @staticmethod
    def build_filter_metadata(
        filter_type: str,
        filter_value: Any,
    ) -> Dict[str, Any]:
        """
        Build metadata about a filter for logging and tracing.
        
        Args:
            filter_type: The filter type identifier
            filter_value: The filter value
            
        Returns:
            Dictionary with filter metadata
        """
        filter_details = FilterEngine.get_filter_details(filter_type)
        
        return {
            "filter_type": filter_type,
            "table": filter_details.table if filter_details else None,
            "search_column": filter_details.search_column if filter_details else None,
            "search_type": FilterEngine.get_filter_search_type(filter_type),
            "filter_mode": FilterEngine.get_filter_mode(filter_type),
            "value_sample": (
                str(filter_value)[:50] + "..."
                if filter_value and len(str(filter_value)) > 50
                else str(filter_value)
            ),
        }

