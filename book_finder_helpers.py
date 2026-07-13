import logging
import re
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator, ValidationError

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


class BookFinderRequestSchema(BaseModel):
    """
    Pydantic schema for validating incoming Book Finder Agent requests.
    Enforces required fields (search_query, session_id) and normalizes optional filter parameters.
    """
    
    search_query: str
    session_id: str
    book_summary_details: Optional[str] = None
    genre_details: Optional[str] = None
    author_details: Optional[str] = None
    publication_date_details: Optional[Dict[str, Any]] = None
    isbn_details: Optional[str] = None
    publisher_details: Optional[str] = None
    audience_details: Optional[str] = None
    
    class Config:
        extra = "ignore"
    
    @field_validator('search_query', 'session_id', mode='before')
    @classmethod
    def validate_non_empty_strings(cls, v):
        if isinstance(v, str):
            if not v.strip():
                raise ValueError('Field cannot be empty or whitespace-only')
            return v.strip()
        if v is None:
            raise ValueError('Field is required and cannot be None')
        return v
    
    def get_run_params(self) -> Dict[str, Any]:
        """
        Returns a dictionary containing only non-None filter parameters.
        Used to extract filters for downstream retrieval logic.
        
        Returns:
            Dict[str, Any]: Dictionary of non-None filter parameters
        """
        filters = {}
        if self.book_summary_details is not None:
            filters['book_summary_details'] = self.book_summary_details
        if self.genre_details is not None:
            filters['genre_details'] = self.genre_details
        if self.author_details is not None:
            filters['author_details'] = self.author_details
        if self.publication_date_details is not None:
            filters['publication_date_details'] = self.publication_date_details
        if self.isbn_details is not None:
            filters['isbn_details'] = self.isbn_details
        if self.publisher_details is not None:
            filters['publisher_details'] = self.publisher_details
        if self.audience_details is not None:
            filters['audience_details'] = self.audience_details
        return filters


class InputValidationError(Exception):
    """
    Custom exception for input validation errors in the Book Finder Agent.
    """
    pass


def validate_request(payload: Dict[str, Any]) -> BookFinderRequestSchema:
    """
    Validates an incoming request payload against the BookFinderRequestSchema.
    
    Args:
        payload: Dictionary containing request parameters
        
    Returns:
        BookFinderRequestSchema: Validated schema instance
        
    Raises:
        ValidationError: If required fields are missing or invalid
    """
    try:
        return BookFinderRequestSchema(**payload)
    except ValidationError as e:
        logging.error(f"Request validation failed: {e}")
        raise


def generate_citations(
    retrieved_books: List[Dict[str, Any]],
    response_text: str,
    uuid_mapping: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract citation markers from LLM response and link to supporting book metadata.
    
    Parses the response text to identify citation placeholders or markers (e.g., [BOOK_1],
    [AUTHOR_2], or inline markdown links), looks up corresponding books in retrieved_books
    using ID mapping, extracts supporting metadata (summary, genres, excerpts, etc.),
    and constructs citation objects with evidence-backed sources.
    
    Args:
        retrieved_books: List of book dicts with metadata and supporting_excerpts
        response_text: LLM-generated response text that may contain citation markers
        uuid_mapping: Optional dict mapping temporary IDs to permanent book UUIDs
        
    Returns:
        List[Dict]: Citation dicts with keys:
            - citation_number: Sequential citation number (1, 2, 3, ...)
            - source_book_id: ID of the source book
            - source_type: Metadata field name (summary, genres, author_details, etc.)
            - highlighted_text: Best-matching excerpt from supporting_excerpts
            - citation_score: Confidence score (0.0-1.0) based on matching quality
            - metadata: Book metadata dict with title, authors, genres, etc.
    """
    citations = []
    
    try:
        logging.info(f"Generating citations from response text (length: {len(response_text)})")
        
        if not response_text or not isinstance(response_text, str):
            logging.warning("Response text is empty or invalid. Returning empty citations.")
            return []
        
        if not retrieved_books or not isinstance(retrieved_books, list):
            logging.warning("No books provided for citation generation. Returning empty citations.")
            return []
        
        # Extract citation markers from response text
        # Pattern 1: [BOOK_N] format
        book_pattern = r'\[BOOK_(\d+)\]'
        book_matches = re.finditer(book_pattern, response_text)
        
        citation_counter = 1
        processed_ids = set()
        
        for match in book_matches:
            book_index = int(match.group(1)) - 1  # Convert 1-indexed to 0-indexed
            
            # Skip if already processed or out of range
            if book_index in processed_ids or book_index < 0 or book_index >= len(retrieved_books):
                continue
            
            processed_ids.add(book_index)
            
            # Get the book data
            book_dict = retrieved_books[book_index]
            book_id = None
            book_data = None
            
            # Extract book_id and data from the nested dict structure
            for bid, data in book_dict.items():
                book_id = bid
                book_data = data
                break
            
            if not book_data:
                logging.warning(f"Skipping citation: book at index {book_index} has no data")
                continue
            
            # Extract supporting excerpt using fuzzy matching on relevant text
            supporting_excerpts = book_data.get("supporting_excerpts", [])
            best_excerpt = ""
            best_score = 0.0
            
            if supporting_excerpts and isinstance(supporting_excerpts, list):
                # Find best-matching excerpt from the response context
                # Look for text near the citation marker
                citation_start = max(0, match.start() - 200)
                citation_end = min(len(response_text), match.end() + 200)
                context_window = response_text[citation_start:citation_end]
                
                for excerpt in supporting_excerpts:
                    if not isinstance(excerpt, dict):
                        continue
                    excerpt_text = excerpt.get("text") or excerpt.get("chunk_text") or ""
                    if not excerpt_text:
                        continue
                    
                    # Calculate fuzzy match score between context window and excerpt
                    if fuzz:
                        score = fuzz.partial_ratio(excerpt_text, context_window) / 100.0
                    else:
                        # Fallback: simple substring matching
                        score = 1.0 if excerpt_text.lower() in context_window.lower() else 0.0
                    
                    if score > best_score:
                        best_score = score
                        best_excerpt = excerpt_text[:200]  # Truncate to 200 chars
            
            # If no supporting excerpts, use book summary
            if not best_excerpt:
                summary = book_data.get("summary") or ""
                if summary:
                    best_excerpt = summary[:200]
                    best_score = 0.7  # Lower confidence for summary-based citation
            
            # Construct citation object
            citation = {
                "citation_number": citation_counter,
                "source_book_id": str(book_id),
                "source_type": "supporting_excerpts" if best_score > 0.5 else "summary",
                "highlighted_text": best_excerpt,
                "citation_score": min(best_score, 1.0),
                "metadata": {
                    "title": book_data.get("title", "Unknown"),
                    "authors": book_data.get("authors", []),
                    "genres": book_data.get("genres", []),
                    "isbn": book_data.get("isbn"),
                    "publisher": book_data.get("publisher"),
                    "publication_date": book_data.get("publication_date"),
                }
            }
            
            citations.append(citation)
            citation_counter += 1
        
        logging.info(f"Generated {len(citations)} citations from response text")
        return citations
        
    except Exception as e:
        logging.error(f"Error generating citations: {e}", exc_info=True)
        # Return empty citations list on error instead of raising
        return []

