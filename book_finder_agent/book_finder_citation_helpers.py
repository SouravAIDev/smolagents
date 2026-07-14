import logging
import re
from typing import Dict, List, Optional, Tuple


class CitationUtils:
    """Citation extraction, verification, and formatting utilities."""

    # Regex pattern to extract markdown-style citations: [text](url)
    CITATION_PATTERN = r'\[([^\]]+)\]\(([^)]+)\)'
    
    # ISBN pattern in URLs
    ISBN_PATTERN = r'isbn=([\w\-]+)'
    
    @staticmethod
    def extract_citations_from_response(response_text: str) -> List[Dict[str, str]]:
        """
        Extract all citations from LLM response using markdown link pattern.
        
        Args:
            response_text: The LLM-generated response text
            
        Returns:
            List of dicts with keys: cited_text, url, isbn, source_chunk_id
        """
        try:
            citations = []
            
            # Find all markdown-style links [text](url)
            matches = re.finditer(CitationUtils.CITATION_PATTERN, response_text)
            
            for match in matches:
                cited_text = match.group(1).strip()
                url = match.group(2).strip()
                
                # Extract ISBN from URL
                isbn_match = re.search(CitationUtils.ISBN_PATTERN, url)
                isbn = isbn_match.group(1) if isbn_match else None
                
                # Extract source chunk ID if present
                chunk_match = re.search(r'chunk[_id]*=([\w\-]+)', url, re.IGNORECASE)
                chunk_id = chunk_match.group(1) if chunk_match else None
                
                citation = {
                    'cited_text': cited_text,
                    'url': url,
                    'isbn': isbn,
                    'source_chunk_id': chunk_id,
                    'verified': False,
                    'retry_count': 0,
                }
                citations.append(citation)
            
            logging.info(f"Extracted {len(citations)} citations from response")
            return citations
            
        except Exception as e:
            logging.error(f"Error extracting citations: {e}")
            return []

    @staticmethod
    def verify_citation(
        cited_text: str,
        source_text: str,
        max_retries: int = 1,
    ) -> bool:
        """
        Verify that cited text exists as a contiguous substring in source.
        Implements retry logic for transient mismatches.
        
        Args:
            cited_text: The text snippet cited in the response
            source_text: The original source text to verify against
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if citation is verified, False otherwise
        """
        try:
            if not cited_text or not source_text:
                logging.warning("Empty cited_text or source_text")
                return False
            
            # Direct substring match (case-insensitive)
            cited_text_clean = cited_text.strip().lower()
            source_text_clean = source_text.lower()
            
            # Attempt 1: Exact substring match
            if cited_text_clean in source_text_clean:
                logging.debug(f"Citation verified: '{cited_text[:50]}...'")
                return True
            
            # Attempt 2: Fuzzy match with whitespace normalization
            cited_normalized = ' '.join(cited_text_clean.split())
            source_normalized = ' '.join(source_text_clean.split())
            
            if cited_normalized in source_normalized:
                logging.debug(f"Citation verified (normalized): '{cited_text[:50]}...'")
                return True
            
            # Attempt 3: Partial match if retry allowed
            if max_retries > 0:
                # Try removing punctuation
                import string
                translator = str.maketrans('', '', string.punctuation)
                cited_nopunc = cited_normalized.translate(translator)
                source_nopunc = source_normalized.translate(translator)
                
                if cited_nopunc in source_nopunc:
                    logging.debug(f"Citation verified (punctuation-stripped): '{cited_text[:50]}...'")
                    return True
            
            logging.warning(f"Citation not verified: '{cited_text[:50]}...'")
            return False
            
        except Exception as e:
            logging.error(f"Error verifying citation: {e}")
            return False

    @staticmethod
    def strip_unverified_citations(
        response_text: str,
        citations: List[Dict[str, any]],
    ) -> str:
        """
        Remove citation links for citations that failed verification.
        Leaves the text intact but removes the markdown link formatting.
        
        Args:
            response_text: Original LLM response
            citations: List of citation dicts with 'verified' flag
            
        Returns:
            Response text with unverified citations stripped
        """
        try:
            modified_text = response_text
            verified_citations = [c for c in citations if c.get('verified', False)]
            
            # Build set of verified citation texts
            verified_texts = {c.get('cited_text') for c in verified_citations}
            
            # Find all citations in original text
            matches = list(re.finditer(CitationUtils.CITATION_PATTERN, response_text))
            
            # Process matches in reverse order to preserve indices
            for match in reversed(matches):
                cited_text = match.group(1).strip()
                
                # If this citation was not verified, replace [text](url) with just text
                if cited_text not in verified_texts:
                    # Replace markdown link with plain text
                    plain_text = cited_text
                    modified_text = modified_text[:match.start()] + plain_text + modified_text[match.end():]
                    logging.debug(f"Stripped unverified citation: '{cited_text}'")
            
            logging.info(f"Stripped {len(matches) - len(verified_citations)} unverified citations")
            return modified_text
            
        except Exception as e:
            logging.error(f"Error stripping unverified citations: {e}")
            return response_text

    @staticmethod
    def convert_markdown_bold_to_html(text: str) -> str:
        """
        Convert markdown bold syntax (**text**) to HTML <strong> tags.
        
        Args:
            text: Text with markdown bold formatting
            
        Returns:
            Text with HTML strong tags
        """
        try:
            if not text:
                return ""
            return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text, flags=re.DOTALL)
        except Exception as e:
            logging.error(f"Error converting markdown: {e}")
            return text

    @staticmethod
    def format_citations_for_output(citations: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Format citations into a clean output structure.
        
        Args:
            citations: List of citation dictionaries
            
        Returns:
            Formatted citations list
        """
        try:
            formatted = []
            
            for citation in citations:
                if citation.get('verified', False):
                    formatted.append({
                        'text': citation.get('cited_text', ''),
                        'source_isbn': citation.get('isbn', 'UNKNOWN'),
                        'source_chunk_id': citation.get('source_chunk_id'),
                        'url': citation.get('url', ''),
                    })
            
            logging.info(f"Formatted {len(formatted)} citations for output")
            return formatted
            
        except Exception as e:
            logging.error(f"Error formatting citations: {e}")
            return []

    @staticmethod
    def handle_missing_source_fallback(
        cited_text: str,
        book_title: str,
        isbn: str,
    ) -> Dict[str, str]:
        """
        Generate fallback citation when source text is unavailable.
        
        Args:
            cited_text: The cited text snippet
            book_title: Title of the source book
            isbn: ISBN of the source book
            
        Returns:
            Fallback citation dict
        """
        return {
            'text': cited_text,
            'source_isbn': isbn,
            'source_title': book_title,
            'verified': False,
            'fallback': True,
            'url': f'?isbn={isbn}',
        }

