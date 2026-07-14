"""Utilities for book data transformation, normalization, and summary generation.

Provides functions for:
- Generating XML-formatted summaries of books for LLM context
- Extracting and formatting book metadata
- Normalizing book data structures
- Formatting book details for display
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime


def generate_books_summary(
    target: str,
    books: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Generate a summary of books for LLM context.
    
    Formats a list of book candidates into a structured summary that
    can be embedded in LLM prompts for generating recommendations.
    
    Args:
        target: Either 'book' or 'section' indicating retrieval target
        books: List of book dictionaries with metadata
        
    Returns:
        Dictionary containing summary statistics and formatted books
        
    Example:
        >>> books = [
        ...     {'isbn': '978-0-123-45678-9', 'title': 'Example Book'},
        ...     {'isbn': '978-0-123-45678-0', 'title': 'Another Book'}
        ... ]
        >>> summary = generate_books_summary('book', books)
        >>> summary['count']
        2
    """
    try:
        if not books or not isinstance(books, list):
            return {
                'count': 0,
                'target': target,
                'summary': 'No books found',
                'books': []
            }
        
        formatted_books = []
        for idx, book in enumerate(books, 1):
            formatted_book = {
                'index': idx,
                'isbn': book.get('isbn', 'N/A'),
                'title': book.get('title', 'Unknown Title'),
                'author': book.get('author', 'Unknown Author'),
                'genre': book.get('genre', 'Unknown Genre'),
                'relevance_score': book.get('context_score', 0),
            }
            formatted_books.append(formatted_book)
        
        summary_text = f"Found {len(formatted_books)} {target}s matching your query."
        
        return {
            'count': len(formatted_books),
            'target': target,
            'summary': summary_text,
            'books': formatted_books
        }
        
    except Exception as e:
        logging.error(f"Error generating books summary: {e}", exc_info=True)
        return {
            'count': 0,
            'target': target,
            'summary': 'Error processing books',
            'books': []
        }


def format_book_details(book: Dict[str, Any]) -> Dict[str, Any]:
    """Format a book record for display.
    
    Normalizes field names, formats dates, and ensures all fields
    are properly typed and escaped for safe display.
    
    Args:
        book: Raw book data dictionary from database
        
    Returns:
        Formatted book dictionary
    """
    if not book:
        return {}
    
    try:
        formatted = {}
        
        # Standard fields
        for field in ['isbn', 'title', 'author', 'genre', 'publisher']:
            value = book.get(field, '')
            formatted[field] = str(value) if value else ''
        
        # Numeric fields
        for field in ['publication_year', 'pages', 'context_score']:
            value = book.get(field)
            if value is not None:
                try:
                    formatted[field] = float(value) if isinstance(value, (int, float)) else 0
                except (ValueError, TypeError):
                    formatted[field] = 0
        
        # Date fields
        for field in ['publication_date', 'release_date']:
            value = book.get(field)
            if value:
                formatted[field] = _format_date(value)
        
        # Text fields (escape for safe HTML/XML rendering)
        for field in ['summary', 'description', 'metadata']:
            value = book.get(field, '')
            if value:
                formatted[field] = _escape_xml_text(str(value))
        
        return formatted
        
    except Exception as e:
        logging.error(f"Error formatting book details: {e}", exc_info=True)
        return book  # Return original if formatting fails


def extract_book_metadata(book: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and flatten book metadata.
    
    Pulls nested metadata into a flat structure suitable for
    display or further processing.
    
    Args:
        book: Book data dictionary (may contain nested metadata)
        
    Returns:
        Flattened metadata dictionary
    """
    if not book:
        return {}
    
    metadata = {}
    
    # Extract top-level metadata fields
    direct_fields = ['isbn', 'title', 'author', 'genre', 'publisher', 'publication_year']
    for field in direct_fields:
        if field in book:
            metadata[field] = book[field]
    
    # Extract nested metadata if present
    if 'metadata' in book and isinstance(book['metadata'], dict):
        for key, value in book['metadata'].items():
            metadata[f'meta_{key}'] = value
    
    # Extract book details (from reference agent pattern)
    if 'book_details' in book and isinstance(book['book_details'], list):
        if book['book_details']:
            details = book['book_details'][0]
            for key, value in details.items():
                if key not in metadata:  # Avoid overwrites
                    metadata[f'detail_{key}'] = value
    
    return metadata


def normalize_book_data(books: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize a list of book records.
    
    Applies consistent formatting, removes duplicates, and ensures
    all required fields are present.
    
    Args:
        books: List of raw book dictionaries
        
    Returns:
        List of normalized book dictionaries
    """
    if not books:
        return []
    
    normalized = []
    seen_isbns = set()
    
    for book in books:
        if not isinstance(book, dict):
            continue
        
        try:
            # Format the book
            formatted = format_book_details(book)
            
            # Skip duplicates by ISBN
            isbn = formatted.get('isbn', '')
            if isbn and isbn in seen_isbns:
                logging.debug(f"Skipping duplicate book: {isbn}")
                continue
            if isbn:
                seen_isbns.add(isbn)
            
            # Ensure required fields are present
            if not formatted.get('title'):
                formatted['title'] = 'Unknown Title'
            if not formatted.get('author'):
                formatted['author'] = 'Unknown Author'
            
            normalized.append(formatted)
            
        except Exception as e:
            logging.warning(f"Error normalizing book data: {e}")
            continue
    
    return normalized


# ============================================================================
# PRIVATE HELPER FUNCTIONS
# ============================================================================

def _format_date(date_value: Any) -> str:
    """Format a date value for display.
    
    Handles multiple input types (datetime, string, int timestamps).
    
    Args:
        date_value: Date in various formats
        
    Returns:
        Formatted date string (YYYY-MM-DD)
    """
    try:
        if isinstance(date_value, datetime):
            return date_value.strftime('%Y-%m-%d')
        
        if isinstance(date_value, str):
            # Try to parse if not already formatted
            if len(date_value) == 10 and date_value.count('-') == 2:
                return date_value  # Already formatted
            try:
                dt = datetime.fromisoformat(date_value)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                return date_value  # Return as-is if unparseable
        
        if isinstance(date_value, (int, float)):
            # Assume Unix timestamp
            dt = datetime.fromtimestamp(date_value)
            return dt.strftime('%Y-%m-%d')
        
        return str(date_value)
        
    except Exception as e:
        logging.warning(f"Error formatting date {date_value}: {e}")
        return str(date_value)


def _escape_xml_text(text: str) -> str:
    """Escape special XML/HTML characters in text.
    
    Prevents injection attacks and malformed markup.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for XML/HTML context
    """
    if not isinstance(text, str):
        return str(text)
    
    # Replace special characters
    replacements = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    }
    
    result = text
    for char, escape in replacements.items():
        result = result.replace(char, escape)
    
    return result

