import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from psycopg2 import sql, extensions
from psycopg2.extras import RealDictCursor
import json


class DatabaseUtility:
    """
    Core utility class for executing database operations against AlloyDB.
    Provides methods for parameterized query execution, result parsing,
    and data normalization.
    """

    @staticmethod
    def execute_parameterized_query(
        connection: extensions.connection,
        query: str,
        params: Tuple = (),
        fetch_one: bool = False,
        fetch_all: bool = True,
        return_dict: bool = True
    ) -> Any:
        """
        Execute a parameterized SQL query safely against AlloyDB.

        Args:
            connection: psycopg2 database connection object
            query: SQL query string with %s placeholders for parameters
            params: Tuple of parameters to bind to the query
            fetch_one: If True, return only the first row
            fetch_all: If True, return all rows (default)
            return_dict: If True, return rows as dicts; if False, return tuples

        Returns:
            Query result (single row dict, list of dicts, or None based on flags)

        Raises:
            Exception: If database execution fails
        """
        cursor_factory = RealDictCursor if return_dict else None
        try:
            with connection.cursor(cursor_factory=cursor_factory) as cursor:
                cursor.execute(query, params)
                if fetch_one:
                    return cursor.fetchone()
                elif fetch_all:
                    return cursor.fetchall()
                else:
                    return cursor.rowcount
        except Exception as e:
            logging.error(f"Database query execution failed: {e}")
            raise

    @staticmethod
    def execute_transaction(
        connection: extensions.connection,
        queries: List[Tuple[str, Tuple]],
        autocommit: bool = True
    ) -> bool:
        """
        Execute multiple SQL queries in a single transaction.

        Args:
            connection: psycopg2 database connection object
            queries: List of (query_string, params_tuple) tuples
            autocommit: If True, commit after execution; if False, caller must commit

        Returns:
            bool: True if transaction succeeded, False otherwise
        """
        try:
            with connection.cursor() as cursor:
                for query, params in queries:
                    cursor.execute(query, params)
            if autocommit:
                connection.commit()
            return True
        except Exception as e:
            logging.error(f"Transaction execution failed: {e}")
            connection.rollback()
            return False

    @staticmethod
    def normalize_uuid(value: Optional[str]) -> Optional[str]:
        """
        Normalize a UUID value to standard format (lowercase).

        Args:
            value: UUID string (may be uppercase, with or without hyphens)

        Returns:
            Normalized UUID string, or None if input is None
        """
        if value is None:
            return None
        try:
            # Validate and normalize UUID
            normalized = str(uuid.UUID(str(value))).lower()
            return normalized
        except (ValueError, AttributeError) as e:
            logging.warning(f"Could not normalize UUID '{value}': {e}")
            return None

    @staticmethod
    def format_datetime(value: Optional[datetime]) -> Optional[str]:
        """
        Format a datetime object to ISO 8601 string.

        Args:
            value: datetime object or string

        Returns:
            ISO 8601 formatted string (YYYY-MM-DDTHH:MM:SSZ), or None if input is None
        """
        if value is None:
            return None
        try:
            if isinstance(value, datetime):
                return value.isoformat() + "Z"
            elif isinstance(value, str):
                # Attempt to parse and re-format
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.isoformat() + "Z"
            else:
                logging.warning(f"Could not format datetime value: {value}")
                return None
        except Exception as e:
            logging.warning(f"Datetime formatting error: {e}")
            return None

    @staticmethod
    def format_isbn(value: Optional[str]) -> Optional[str]:
        """
        Normalize ISBN-10 or ISBN-13 format.

        Args:
            value: ISBN string (with or without hyphens/spaces)

        Returns:
            Cleaned ISBN (hyphens/spaces removed), or None if input is None
        """
        if value is None:
            return None
        try:
            # Remove hyphens and spaces
            cleaned = value.replace("-", "").replace(" ", "").upper()
            # Validate length (10 or 13 digits)
            if len(cleaned) in (10, 13) and cleaned.isdigit():
                return cleaned
            else:
                logging.warning(f"Invalid ISBN format: {value}")
                return None
        except Exception as e:
            logging.warning(f"ISBN formatting error: {e}")
            return None

    @staticmethod
    def build_filter_where_clause(
        filters: Dict[str, Any],
        base_table: str = "books"
    ) -> Tuple[str, List]:
        """
        Dynamically construct WHERE clause conditions from filter parameters.

        Args:
            filters: Dictionary of filter key-value pairs from BookFinderRequestSchema
            base_table: Primary table name for unprefixed columns

        Returns:
            Tuple of (where_clause_sql, params_list) for parameterized query
        """
        conditions = []
        params = []

        # Map filter keys to SQL conditions
        filter_mappings = {
            "author_details": (f"{base_table}.author_name ILIKE %s", "author_details"),
            "genre_details": (f"{base_table}.genre ILIKE %s", "genre_details"),
            "publisher_details": (f"{base_table}.publisher_name ILIKE %s", "publisher_details"),
            "isbn_details": (f"{base_table}.isbn = %s", "isbn_details"),
            "audience_details": (f"{base_table}.audience_type ILIKE %s", "audience_details"),
        }

        for key, (condition_template, filter_key) in filter_mappings.items():
            if filter_key in filters and filters[filter_key] is not None:
                value = filters[filter_key]
                # Wrap ILIKE patterns with wildcards for partial matching
                if "ILIKE" in condition_template:
                    params.append(f"%{value}%")
                else:
                    params.append(value)
                conditions.append(condition_template)

        # Handle publication_date_details range filter
        if "publication_date_details" in filters and filters["publication_date_details"]:
            date_filter = filters["publication_date_details"]
            if isinstance(date_filter, dict):
                if "start" in date_filter:
                    conditions.append(f"{base_table}.publication_year >= %s")
                    params.append(date_filter["start"])
                if "end" in date_filter:
                    conditions.append(f"{base_table}.publication_year <= %s")
                    params.append(date_filter["end"])

        # Join all conditions with AND
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params

    @staticmethod
    def build_embedding_similarity_clause(
        embedding_vector: List[float],
        table_alias: str = "t",
        threshold: float = 0.65,
        similarity_column: str = "embedding"
    ) -> Tuple[str, List]:
        """
        Build a PostgreSQL pgvector cosine similarity clause.

        Args:
            embedding_vector: List of floats representing the query embedding
            table_alias: Table alias for the embedding column
            threshold: Minimum cosine similarity threshold (0.0-1.0)
            similarity_column: Column name containing the embedding vector

        Returns:
            Tuple of (similarity_sql, [embedding_vector, threshold]) for parameterized query
        """
        # PostgreSQL pgvector uses <=> operator for cosine distance
        # Cosine similarity = 1 - cosine_distance
        # For similarity threshold, we need: (1 - distance) >= threshold
        # Which equals: distance <= (1 - threshold)
        distance_threshold = 1.0 - threshold

        similarity_clause = (
            f"(1 - ({table_alias}.{similarity_column} <=> %s::vector)) >= %s"
        )

        return similarity_clause, [embedding_vector, threshold]

    @staticmethod
    def extract_book_ids_from_results(rows: List[Dict[str, Any]]) -> List[str]:
        """
        Extract unique book IDs from query result set.

        Args:
            rows: List of result row dicts from database

        Returns:
            List of unique book_id strings
        """
        if not rows:
            return []

        book_ids = []
        seen = set()

        for row in rows:
            book_id = row.get("book_id")
            if book_id and book_id not in seen:
                book_ids.append(book_id)
                seen.add(book_id)

        return book_ids

    @staticmethod
    def parse_book_record(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a database row into a normalized Book domain object.

        Args:
            row: Database row dict

        Returns:
            Normalized book record dict with fields:
            - book_id: Normalized UUID
            - title: Book title
            - authors: Comma-separated author names
            - genres: Comma-separated genre names
            - isbn: Normalized ISBN
            - publication_date: ISO 8601 formatted date
            - summary: Book summary text
            - publisher: Publisher name
            - audience: Target audience
            - additional metadata as present
        """
        if not row:
            return {}

        parsed = {
            "book_id": DatabaseUtility.normalize_uuid(row.get("book_id")),
            "title": row.get("title", ""),
            "authors": row.get("all_authors") or row.get("author_name", ""),
            "genres": row.get("all_genres") or row.get("genre_name", ""),
            "isbn": DatabaseUtility.format_isbn(row.get("isbn")),
            "isbn_13": DatabaseUtility.format_isbn(row.get("isbn_13")),
            "publication_date": DatabaseUtility.format_datetime(row.get("publication_date")),
            "publication_year": row.get("publication_year"),
            "summary": row.get("summary_text") or row.get("summary", ""),
            "publisher": row.get("publisher_name", ""),
            "audience": row.get("audience_type", ""),
            "contributors": row.get("all_contributors") or row.get("contributor_name", ""),
            "prizes": row.get("all_prizes") or row.get("prize_name", ""),
            "locations": row.get("all_locations") or row.get("location_name", ""),
        }

        # Remove None values for cleaner output
        return {k: v for k, v in parsed.items() if v is not None}

    @staticmethod
    def calculate_relevance_score(
        embedding_similarity: float = 0.0,
        filter_match_count: int = 0,
        max_filters: int = 8,
        keyword_boost: float = 0.0,
        embedding_weight: float = 0.5,
        filter_weight: float = 0.3,
        keyword_weight: float = 0.2
    ) -> float:
        """
        Calculate final relevance score from multiple signals.

        Args:
            embedding_similarity: Cosine similarity score (0.0-1.0)
            filter_match_count: Number of filters matched
            max_filters: Maximum possible filter matches
            keyword_boost: Keyword boost score (0.0-1.0)
            embedding_weight: Weight for embedding similarity (0.0-1.0)
            filter_weight: Weight for filter matches (0.0-1.0)
            keyword_weight: Weight for keyword boost (0.0-1.0)

        Returns:
            float: Normalized relevance score (0.0-1.0)
        """
        # Normalize filter match count to 0.0-1.0 range
        filter_score = min(1.0, filter_match_count / max_filters) if max_filters > 0 else 0.0

        # Weighted combination of signals
        total_weight = embedding_weight + filter_weight + keyword_weight
        if total_weight == 0:
            return 0.0

        # Normalize weights to sum to 1.0
        embedding_weight_norm = embedding_weight / total_weight
        filter_weight_norm = filter_weight / total_weight
        keyword_weight_norm = keyword_weight / total_weight

        relevance = (
            (embedding_similarity * embedding_weight_norm) +
            (filter_score * filter_weight_norm) +
            (keyword_boost * keyword_weight_norm)
        )

        return max(0.0, min(1.0, relevance))  # Clamp to [0.0, 1.0]

    @staticmethod
    def normalize_scores(
        items: List[Dict[str, Any]],
        score_key: str = "relevance_score"
    ) -> List[Dict[str, Any]]:
        """
        Normalize scores across a list of items to 0.0-1.0 range.

        Args:
            items: List of result dicts containing score_key
            score_key: Key name for score field in each item

        Returns:
            List of items with normalized scores
        """
        if not items:
            return []

        scores = [item.get(score_key, 0.0) for item in items]
        min_score = min(scores) if scores else 0.0
        max_score = max(scores) if scores else 0.0

        # Avoid division by zero
        if max_score == min_score:
            normalized_items = [{**item, score_key: 1.0 if item.get(score_key) else 0.0} for item in items]
        else:
            normalized_items = [
                {**item, score_key: (item.get(score_key, 0.0) - min_score) / (max_score - min_score)}
                for item in items
            ]

        return normalized_items

    @staticmethod
    def load_sql_template(template_path: str) -> str:
        """
        Load a SQL template from file.

        Args:
            template_path: Path to SQL template file relative to queries directory

        Returns:
            str: SQL query template content

        Raises:
            FileNotFoundError: If template file does not exist
        """
        import os
        queries_dir = os.path.join(os.path.dirname(__file__), "queries")
        full_path = os.path.join(queries_dir, template_path)

        try:
            with open(full_path, "r") as f:
                return f.read().strip()
        except FileNotFoundError as e:
            logging.error(f"SQL template not found: {full_path}")
            raise
        except Exception as e:
            logging.error(f"Error loading SQL template: {e}")
            raise


def format_datetimes_for_llm(records: List[Dict]) -> Tuple[List[Dict], Dict[str, str]]:
    """
    Normalize datetime and UUID fields in records for LLM consumption.
    
    Converts datetime/date fields to ISO 8601 format (YYYY-MM-DD).
    Replaces UUID fields with temporary numeric IDs and returns a mapping
    for citation generation.
    
    Args:
        records: List of book record dictionaries
        
    Returns:
        Tuple of (normalized_records, uuid_to_id_mapping) where mapping is
        a dict mapping UUID strings to temporary numeric IDs
    """
    try:
        uuid_mapping = {}  # Maps UUID strings to temporary numeric IDs
        next_id = 1000  # Start temporary IDs at 1000 to avoid collision
        datetime_fields = {
            'publication_date', 'created_at', 'updated_at', 'release_date',
            'effective_date', 'expiration_date'
        }
        uuid_fields = {'book_id', 'author_id', 'contributor_id', 'publisher_id', 'genre_id'}
        
        normalized_records = []
        
        for record in records:
            if not isinstance(record, dict):
                continue
            
            normalized_record = {}
            
            for key, value in record.items():
                try:
                    # Handle datetime fields
                    if key in datetime_fields and value is not None:
                        if isinstance(value, datetime):
                            normalized_record[key] = value.strftime("%Y-%m-%d")
                        elif isinstance(value, str):
                            # Try to parse and reformat
                            try:
                                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                                normalized_record[key] = dt.strftime("%Y-%m-%d")
                            except:
                                normalized_record[key] = value  # Keep as-is if parsing fails
                        else:
                            normalized_record[key] = value
                    
                    # Handle UUID fields - replace with temp numeric ID
                    elif key in uuid_fields and value is not None:
                        uuid_str = str(value).lower().strip()
                        if uuid_str not in uuid_mapping:
                            uuid_mapping[uuid_str] = str(next_id)
                            next_id += 1
                        normalized_record[key] = uuid_mapping[uuid_str]
                    
                    else:
                        normalized_record[key] = value
                
                except Exception as e:
                    logging.warning(f"Error normalizing field {key}: {e}")
                    normalized_record[key] = value  # Keep original on error
            
            normalized_records.append(normalized_record)
        
        logging.info(f"Normalized {len(normalized_records)} records. UUID mapping size: {len(uuid_mapping)}")
        return normalized_records, uuid_mapping
        
    except Exception as e:
        logging.error(f"Error in format_datetimes_for_llm: {e}", exc_info=True)
        # Return original records on error
        return records, {}


def process_filtered_data(filtered_books: Dict[str, Dict]) -> List[Dict]:
    """
    Transform scored books dictionary into a ranked list for response assembly.
    
    Converts books dict to list of single-key dicts, sorts by final_score descending,
    and removes internal scoring fields (similarity_score, document_score) before
    returning to reduce context size for LLM.
    
    Args:
        filtered_books: Dict mapping book_id -> book_data with scores
        
    Returns:
        List of dicts, each dict is {book_id: book_data}, sorted by score descending
    """
    try:
        # Convert dict to list of single-key dicts
        book_list = [
            {book_id: book_data}
            for book_id, book_data in filtered_books.items()
        ]
        
        # Sort by final_score descending
        book_list.sort(
            key=lambda x: list(x.values())[0].get("final_score", 0),
            reverse=True
        )
        
        # Remove internal scoring fields to reduce LLM context
        fields_to_remove = {
            'similarity_score', 'document_score', 'keyword_score',
            'filter_matches', 'similarity_scores', 'relevance_score',
            'embedding_similarity', 'filter_match_count'
        }
        
        for book_dict in book_list:
            for book_id, book_data in book_dict.items():
                for field in fields_to_remove:
                    book_data.pop(field, None)
        
        logging.info(f"Processed {len(book_list)} books into ranked list")
        return book_list
        
    except Exception as e:
        logging.error(f"Error in process_filtered_data: {e}", exc_info=True)
        # Return empty list on error
        return []

