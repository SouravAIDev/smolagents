from datetime import datetime, date
import copy
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple


class BookFinderUtilities:
    """Data parsing, scoring, and response-format helpers for BookFinderAgent."""

    def _process_filtered_data(
        self,
        filtered_books: Dict[str, Dict],
        sort_by_score: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Process and clean filtered book data by:
        - Deep copying the data to avoid mutations
        - Removing unnecessary scoring fields
        - Sorting all documents by their 'final_score' (if enabled)
        
        Args:
            filtered_books (Dict[str, Dict]): Dictionary of books with their metadata.
            sort_by_score (bool): Whether to sort by 'final_score' descending.
        
        Returns:
            List[Dict[str, Any]]: Cleaned and processed list of retrieved documents.
        """
        retrieved_documents = []

        for book_id, book_data in filtered_books.items():
            # Deep copy to avoid mutating original data
            book_copy = copy.deepcopy(book_data)
            
            # Remove unwanted scores
            for field in ["document_score", "keyword_score", "similarity_score", "context_score"]:
                book_copy.pop(field, None)

            # Append processed entry
            retrieved_documents.append({book_id: book_copy})

        # Optionally sort by final_score
        if sort_by_score:
            retrieved_documents.sort(
                key=lambda book_entry: list(book_entry.values())[0].get("final_score", 0),
                reverse=True
            )

        return retrieved_documents


    def _parse_author_names(self, value: Any) -> List[str]:
        """
        Parse author names from DB output into a clean string list.
        
        Args:
            value: Raw value from database (could be list, string, JSON, etc.)
        
        Returns:
            list: Clean list of author name strings
        """
        if value is None:
            return []

        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if item is not None and str(item).strip()]

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []

            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if item is not None and str(item).strip()]
            except Exception:
                pass

            if raw.startswith("{") and raw.endswith("}"):
                inner = raw[1:-1].strip()
                if not inner:
                    return []
                return [part.strip().strip('"') for part in inner.split(",") if part.strip().strip('"')]

        return []


    def _parse_authors(self, value: Any) -> List[Dict[str, Any]]:
        """
        Parse authors into [{author_name, author_id}] format.
        
        Args:
            value: Raw value from database
        
        Returns:
            list: List of author dictionaries with name and ID
        """
        if value is None:
            return []

        parsed_value = value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                parsed_value = json.loads(raw)
            except Exception:
                return []

        if isinstance(parsed_value, dict):
            parsed_value = [parsed_value]

        if not isinstance(parsed_value, list):
            return []

        authors: List[Dict[str, Any]] = []
        for item in parsed_value:
            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except Exception:
                    continue
            if not isinstance(item, dict):
                continue

            author_name = item.get("author_name")
            if author_name:
                authors.append(
                    {
                        "author_name": author_name,
                        "author_id": item.get("author_id"),
                    }
                )
        return authors


    def _format_datetimes_for_llm(
        self, retrieved_for_llm: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Recursively traverse retrieved_for_llm and format all
        datetime/date values to 'MMM-DD-YYYY' (upper-case) format.
        
        Args:
            retrieved_for_llm: List of dictionaries containing book data
        
        Returns:
            list: List with all date values formatted for LLM consumption
        """

        def _format(value: Any) -> Any:
            if isinstance(value, (datetime, date)):
                return value.strftime("%b-%d-%Y").upper()

            if isinstance(value, dict):
                return {k: _format(v) for k, v in value.items()}

            if isinstance(value, list):
                return [_format(v) for v in value]

            return value

        return [_format(doc) for doc in retrieved_for_llm]


    def format_book_id_map(
        self,
        book_id_map: Optional[Dict[str, int]]
    ) -> Dict[int, str]:
        """
        Format book ID mapping from UUID strings to numeric IDs.
        Reverses the mapping direction for use in response construction.
        
        Args:
            book_id_map: Dictionary mapping book UUID to numeric ID
        
        Returns:
            dict: Reversed mapping from numeric ID to UUID
        """
        if not book_id_map:
            return {}
        
        try:
            return {int(v): str(k) for k, v in book_id_map.items()}
        except Exception as e:
            logging.error(f"Error formatting book ID map: {e}")
            return {}


    def reduce_book_rows(
        self,
        filtered_books: Dict[str, Dict],
        threshold: float = 0.3,
        min_rows: int = 8
    ) -> Dict[str, Dict]:
        """
        Reduce book results by removing low-scoring entries while maintaining
        a minimum number of rows.
        
        Args:
            filtered_books: Dictionary of books with scores
            threshold: Score threshold for keeping entries
            min_rows: Minimum number of rows to maintain
        
        Returns:
            dict: Filtered dictionary of books meeting criteria
        """
        if not filtered_books:
            return {}
        
        # Sort books by final score
        sorted_books = sorted(
            filtered_books.items(),
            key=lambda x: x[1].get("final_score", 0),
            reverse=True
        )
        
        # Keep books above threshold or until minimum reached
        reduced_books = {}
        for book_id, book_data in sorted_books:
            score = book_data.get("final_score", 0)
            if score >= threshold or len(reduced_books) < min_rows:
                reduced_books[book_id] = book_data
        
        return reduced_books


    def calculate_final_scores(
        self,
        books: Dict[str, Dict],
        context_weight: float = 0.5,
        document_weight: float = 0.2,
        keyword_weight: float = 0.3,
        chunk_boost: float = 0.2
    ) -> Dict[str, Dict]:
        """
        Calculate final similarity scores for books using weighted combination
        of context, document, and keyword similarity scores.
        
        Args:
            books: Dictionary of books with individual scores
            context_weight: Weight for context similarity (default 0.5)
            document_weight: Weight for document similarity (default 0.2)
            keyword_weight: Weight for keyword similarity (default 0.3)
            chunk_boost: Additional boost if supporting chunks retrieved (default 0.2)
        
        Returns:
            dict: Books dictionary with final_score field populated
        """
        weighted_books = {}
        
        for book_id, book_data in books.items():
            book_copy = copy.deepcopy(book_data)
            
            context_score = book_copy.get("context_score", 0.0)
            document_score = book_copy.get("document_score", 0.0)
            keyword_score = book_copy.get("keyword_score", 0.0)
            
            # Calculate weighted final score
            final_score = (
                context_score * context_weight +
                document_score * document_weight +
                keyword_score * keyword_weight
            )
            
            # Apply chunk boost if supporting excerpts were retrieved
            if book_copy.get("supporting_excerpts") or book_copy.get("has_chunks"):
                final_score += chunk_boost
            
            # Normalize to 0-1 range
            final_score = min(final_score, 1.0)
            book_copy["final_score"] = final_score
            
            weighted_books[book_id] = book_copy
        
        return weighted_books


    def extract_isbn_from_metadata(self, book_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract ISBN from book metadata with multiple fallback strategies.
        
        Args:
            book_data: Dictionary containing book metadata
        
        Returns:
            str: ISBN if found, None otherwise
        """
        # Try direct ISBN field
        isbn = book_data.get("isbn")
        if isbn and isinstance(isbn, str) and isbn.strip():
            return isbn.strip()
        
        # Try ISBN-13
        isbn13 = book_data.get("isbn_13")
        if isbn13 and isinstance(isbn13, str) and isbn13.strip():
            return isbn13.strip()
        
        # Try ISBN-10
        isbn10 = book_data.get("isbn_10")
        if isbn10 and isinstance(isbn10, str) and isbn10.strip():
            return isbn10.strip()
        
        return None


    def normalize_genre(self, genre: str) -> str:
        """
        Normalize genre string for consistent comparison.
        
        Args:
            genre: Raw genre string
        
        Returns:
            str: Normalized genre
        """
        if not genre or not isinstance(genre, str):
            return ""
        
        # Convert to lowercase and strip whitespace
        normalized = genre.lower().strip()
        
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized

