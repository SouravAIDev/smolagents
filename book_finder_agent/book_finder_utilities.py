import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


class BookFinderUtilities:
    """Pure utility functions for data transformation and normalization."""

    @staticmethod
    def normalize_isbn(isbn: Optional[str]) -> Optional[str]:
        """
        Normalize ISBN values by removing hyphens and whitespace.
        Validates basic ISBN format (10 or 13 digits).
        
        Args:
            isbn: ISBN string to normalize
            
        Returns:
            Normalized ISBN or None if invalid
        """
        try:
            if not isbn:
                return None
            
            # Remove hyphens and whitespace
            normalized = isbn.replace('-', '').replace(' ', '').upper()
            
            # Validate length (ISBN-10 or ISBN-13)
            if len(normalized) not in [10, 13]:
                logging.warning(f"Invalid ISBN length: {isbn}")
                return None
            
            # Check if all characters are digits (or X for last digit of ISBN-10)
            if not (normalized[:-1].isdigit() and (normalized[-1].isdigit() or normalized[-1] == 'X' and len(normalized) == 10)):
                logging.warning(f"Invalid ISBN format: {isbn}")
                return None
            
            return normalized
            
        except Exception as e:
            logging.error(f"Error normalizing ISBN: {e}")
            return None

    @staticmethod
    def normalize_uuid(value: Optional[str]) -> Optional[str]:
        """
        Normalize UUID values to standard format.
        
        Args:
            value: UUID string to normalize
            
        Returns:
            Normalized UUID or None if invalid
        """
        try:
            if not value:
                return None
            
            # Try to parse as UUID
            parsed_uuid = uuid.UUID(value)
            return str(parsed_uuid)
            
        except (ValueError, AttributeError):
            logging.warning(f"Invalid UUID format: {value}")
            return None
        except Exception as e:
            logging.error(f"Error normalizing UUID: {e}")
            return None

    @staticmethod
    def parse_datetime(date_string: Optional[str], fmt: str = '%Y-%m-%d') -> Optional[datetime]:
        """
        Parse datetime string to datetime object.
        
        Args:
            date_string: Date string to parse
            fmt: Format string (default: '%Y-%m-%d')
            
        Returns:
            Parsed datetime object or None if invalid
        """
        try:
            if not date_string or not isinstance(date_string, str):
                return None
            
            return datetime.strptime(date_string.strip(), fmt)
            
        except ValueError as e:
            logging.warning(f"Date parsing error for '{date_string}': {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error parsing datetime: {e}")
            return None

    @staticmethod
    def format_datetime(dt: Optional[datetime], fmt: str = '%Y-%m-%d') -> Optional[str]:
        """
        Format datetime object to string.
        
        Args:
            dt: Datetime object to format
            fmt: Format string (default: '%Y-%m-%d')
            
        Returns:
            Formatted datetime string or None if invalid
        """
        try:
            if dt is None:
                return None
            
            if not isinstance(dt, datetime):
                return None
            
            return dt.strftime(fmt)
            
        except Exception as e:
            logging.error(f"Error formatting datetime: {e}")
            return None

    @staticmethod
    def normalize_database_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a database row by cleaning and validating field values.
        
        Args:
            row: Database row dictionary
            
        Returns:
            Normalized row dictionary
        """
        try:
            if not row:
                return {}
            
            normalized = {}
            
            for key, value in row.items():
                # Skip None values
                if value is None:
                    continue
                
                # Normalize ISBN fields
                if 'isbn' in key.lower():
                    normalized[key] = BookFinderUtilities.normalize_isbn(value)
                
                # Normalize UUID fields
                elif 'id' in key.lower() and isinstance(value, str) and len(value) == 36:
                    normalized[key] = BookFinderUtilities.normalize_uuid(value)
                
                # Normalize string whitespace
                elif isinstance(value, str):
                    normalized[key] = value.strip()
                
                # Keep numeric and other types as-is
                else:
                    normalized[key] = value
            
            return normalized
            
        except Exception as e:
            logging.error(f"Error normalizing row: {e}")
            return row

    @staticmethod
    def deduplicate_list_of_dicts(
        items: List[Dict[str, Any]],
        key_field: str,
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate dictionaries from list based on a key field.
        Keeps the first occurrence.
        
        Args:
            items: List of dictionaries
            key_field: Field name to use for deduplication
            
        Returns:
            Deduplicated list
        """
        try:
            if not items:
                return []
            
            seen: Set[str] = set()
            deduplicated = []
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                key_value = item.get(key_field)
                if key_value and key_value not in seen:
                    seen.add(key_value)
                    deduplicated.append(item)
            
            logging.info(f"Deduplicated {len(items)} -> {len(deduplicated)} items")
            return deduplicated
            
        except Exception as e:
            logging.error(f"Error deduplicating list: {e}")
            return items

    @staticmethod
    def calculate_keyword_score(
        query: str,
        text: str,
        min_ngram: int = 1,
        max_ngram: int = 3,
    ) -> float:
        """
        Calculate keyword frequency score using n-gram matching.
        Score normalized to [0, 1] range.
        
        Args:
            query: User's query string
            text: Text to score against
            min_ngram: Minimum n-gram length
            max_ngram: Maximum n-gram length
            
        Returns:
            Normalized keyword frequency score between 0 and 1
        """
        try:
            if not query or not text:
                return 0.0
            
            # Normalize to lowercase
            query_lower = query.lower()
            text_lower = text.lower()
            
            # Remove punctuation and tokenize
            import string
            translator = str.maketrans('', '', string.punctuation)
            query_clean = query_lower.translate(translator)
            text_clean = text_lower.translate(translator)
            
            # Extract n-grams from query
            query_words = query_clean.split()
            matched_count = 0
            total_ngrams = 0
            
            # Check each n-gram size
            for n in range(min_ngram, min(max_ngram + 1, len(query_words) + 1)):
                for i in range(len(query_words) - n + 1):
                    ngram = ' '.join(query_words[i:i+n])
                    total_ngrams += 1
                    
                    # Check if n-gram appears in text
                    if ngram in text_clean:
                        matched_count += 1
            
            # Calculate score: matched / total
            if total_ngrams == 0:
                return 0.0
            
            score = min(1.0, matched_count / total_ngrams)
            return score
            
        except Exception as e:
            logging.error(f"Error calculating keyword score: {e}")
            return 0.0

    @staticmethod
    def normalize_similarity_score(
        raw_score: float,
        min_val: float = 0.0,
        max_val: float = 1.0,
    ) -> float:
        """
        Normalize a raw similarity score to [0, 1] range.
        Handles edge cases like NaN, infinity, and out-of-range values.
        
        Args:
            raw_score: Raw similarity score
            min_val: Minimum value in original range
            max_val: Maximum value in original range
            
        Returns:
            Normalized score in [0, 1] range
        """
        try:
            # Handle None and NaN
            if raw_score is None or (isinstance(raw_score, float) and raw_score != raw_score):
                return 0.0
            
            # Convert to float
            score = float(raw_score)
            
            # Handle infinity
            if score == float('inf') or score == float('-inf'):
                return 0.0
            
            # Normalize to [0, 1]
            if min_val == max_val:
                return 1.0 if score >= min_val else 0.0
            
            normalized = (score - min_val) / (max_val - min_val)
            normalized = max(0.0, min(1.0, normalized))  # Clamp to [0, 1]
            
            return normalized
            
        except (ValueError, TypeError) as e:
            logging.warning(f"Error normalizing score {raw_score}: {e}")
            return 0.0
        except Exception as e:
            logging.error(f"Unexpected error normalizing score: {e}")
            return 0.0

    @staticmethod
    def aggregate_scores(
        scores: Dict[str, float],
        weights: Dict[str, float],
    ) -> float:
        """
        Aggregate multiple scores using configurable weights.
        Validates that weights sum to 1.0.
        
        Args:
            scores: Dict mapping score names to score values
            weights: Dict mapping score names to weight values
            
        Returns:
            Weighted aggregate score
        """
        try:
            if not scores or not weights:
                return 0.0
            
            # Validate weights sum to approximately 1.0
            weight_sum = sum(weights.values())
            if abs(weight_sum - 1.0) > 0.01:
                logging.warning(f"Weights don't sum to 1.0: {weight_sum}")
            
            # Calculate weighted sum
            aggregated = 0.0
            for score_name, score_value in scores.items():
                weight = weights.get(score_name, 0.0)
                aggregated += score_value * weight
            
            # Normalize to [0, 1]
            aggregated = max(0.0, min(1.0, aggregated))
            
            return aggregated
            
        except Exception as e:
            logging.error(f"Error aggregating scores: {e}")
            return 0.0

