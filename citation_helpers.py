import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher


class CitationUtils:
    """Citation generation and parsing utilities for BookFinderAgent."""

    @staticmethod
    def extract_citations_from_response(response_text: str, retrieved_docs: List[Dict]) -> List[Dict[str, Any]]:
        """
        Extract citation references from LLM response and match them to retrieved documents.
        Parses markdown-style citations like [source_1], [source_2], etc.
        
        Args:
            response_text (str): The LLM-generated response containing citations
            retrieved_docs (List[Dict]): List of retrieved book documents
        
        Returns:
            list: List of citation dictionaries with source metadata
        """
        citations = []
        
        try:
            # Pattern to match citations like [source_N] or [citation_N]
            citation_pattern = r'\[(?:source|citation)_(\d+)\]'
            matches = re.finditer(citation_pattern, response_text)
            
            for match in matches:
                source_index = int(match.group(1)) - 1
                
                if source_index < len(retrieved_docs):
                    doc = retrieved_docs[source_index]
                    # Extract book ID (first key in document dict)
                    book_id = next(iter(doc.keys())) if doc else None
                    book_data = doc.get(book_id, {}) if book_id else {}
                    
                    citation = {
                        "source_index": source_index + 1,
                        "book_id": book_id,
                        "title": book_data.get("title", "Unknown Book"),
                        "author": book_data.get("author_name", "Unknown Author"),
                        "isbn": book_data.get("isbn", ""),
                        "excerpt": book_data.get("supporting_excerpts", "")[:200] if book_data.get("supporting_excerpts") else ""
                    }
                    
                    # Avoid duplicate citations
                    if not any(c["book_id"] == book_id for c in citations):
                        citations.append(citation)
            
            logging.info(f"Extracted {len(citations)} citations from response")
            return citations
            
        except Exception as e:
            logging.error(f"Error extracting citations: {e}")
            return []


    @staticmethod
    def format_citation_html(citation: Dict[str, Any]) -> str:
        """
        Format a single citation as HTML for display in frontend.
        
        Args:
            citation (Dict): Citation dictionary with metadata
        
        Returns:
            str: HTML-formatted citation string
        """
        try:
            html = f"<div class='citation'>"
            html += f"<span class='title'>{citation.get('title', 'Unknown')}</span>"
            
            if citation.get('author'):
                html += f" <span class='author'>by {citation.get('author')}</span>"
            
            if citation.get('isbn'):
                html += f" <span class='isbn'>(ISBN: {citation.get('isbn')})</span>"
            
            if citation.get('excerpt'):
                html += f"<p class='excerpt'>\"{citation.get('excerpt')}...\"</p>"
            
            html += "</div>"
            return html
            
        except Exception as e:
            logging.error(f"Error formatting citation HTML: {e}")
            return ""


    @staticmethod
    def find_exact_quote_location(full_text: str, quote: str, threshold: float = 0.9) -> Optional[Dict[str, Any]]:
        """
        Find exact or fuzzy match of a quote within full book text.
        Uses sequence matching for fuzzy matching when exact match fails.
        
        Args:
            full_text (str): The complete book text to search within
            quote (str): The quote to locate
            threshold (float): Similarity threshold for fuzzy matching (0-1)
        
        Returns:
            dict: Location info with start/end positions or None if not found
        """
        try:
            # Try exact match first
            start_idx = full_text.find(quote)
            if start_idx != -1:
                return {
                    "found": True,
                    "method": "exact",
                    "start": start_idx,
                    "end": start_idx + len(quote),
                    "context_start": max(0, start_idx - 50),
                    "context_end": min(len(full_text), start_idx + len(quote) + 50)
                }
            
            # Fallback to fuzzy matching
            matcher = SequenceMatcher(None, full_text, quote)
            ratio = matcher.ratio()
            
            if ratio >= threshold:
                # Find best matching block
                matching_blocks = matcher.get_matching_blocks()
                if matching_blocks:
                    best_block = max(matching_blocks, key=lambda x: x.size)
                    return {
                        "found": True,
                        "method": "fuzzy",
                        "similarity": ratio,
                        "start": best_block.a,
                        "end": best_block.a + best_block.size,
                        "context_start": max(0, best_block.a - 50),
                        "context_end": min(len(full_text), best_block.a + best_block.size + 50)
                    }
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding quote location: {e}")
            return None


    @staticmethod
    def generate_citation_summary(citations: List[Dict[str, Any]]) -> str:
        """
        Generate a text summary of all citations for inclusion in response.
        
        Args:
            citations (List[Dict]): List of citations
        
        Returns:
            str: Formatted citation summary
        """
        if not citations:
            return ""
        
        try:
            summary_lines = ["\nSources Used:"]
            
            for idx, citation in enumerate(citations, 1):
                line = f"{idx}. {citation.get('title', 'Unknown')}"
                
                if citation.get('author'):
                    line += f" by {citation.get('author')}"
                
                if citation.get('isbn'):
                    line += f" (ISBN: {citation.get('isbn')})"
                
                summary_lines.append(line)
            
            return "\n".join(summary_lines)
            
        except Exception as e:
            logging.error(f"Error generating citation summary: {e}")
            return ""


    @staticmethod
    def validate_citation_integrity(citations: List[Dict[str, Any]], retrieved_docs: List[Dict]) -> bool:
        """
        Validate that all citations reference valid retrieved documents.
        
        Args:
            citations (List[Dict]): List of citations to validate
            retrieved_docs (List[Dict]): List of retrieved documents
        
        Returns:
            bool: True if all citations are valid, False otherwise
        """
        try:
            retrieved_ids = set()
            for doc in retrieved_docs:
                book_id = next(iter(doc.keys())) if doc else None
                if book_id:
                    retrieved_ids.add(book_id)
            
            for citation in citations:
                if citation.get("book_id") not in retrieved_ids:
                    logging.warning(f"Citation references non-retrieved book: {citation.get('book_id')}")
                    return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error validating citations: {e}")
            return False


    @staticmethod
    def enrich_citation_with_metadata(citation: Dict[str, Any], book_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich a citation with additional book metadata.
        
        Args:
            citation (Dict): Base citation dictionary
            book_metadata (Dict): Additional book metadata
        
        Returns:
            dict: Enriched citation with additional fields
        """
        enriched = citation.copy()
        
        # Add publisher if available
        if book_metadata.get("publisher_name"):
            enriched["publisher"] = book_metadata.get("publisher_name")
        
        # Add publication year if available
        if book_metadata.get("publication_date"):
            enriched["publication_date"] = book_metadata.get("publication_date")
        
        # Add genre if available
        if book_metadata.get("genre"):
            enriched["genre"] = book_metadata.get("genre")
        
        # Add summary snippet if available
        if book_metadata.get("summary"):
            summary = str(book_metadata.get("summary"))
            enriched["summary_snippet"] = summary[:150] + "..." if len(summary) > 150 else summary
        
        # Add URL/link if available
        if book_metadata.get("book_url"):
            enriched["url"] = book_metadata.get("book_url")
        
        return enriched

