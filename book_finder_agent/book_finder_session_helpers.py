import logging
import json
from typing import Dict, List, Optional, Tuple, Any


class SessionHelpers:
    """Helpers for session-based request routing and state management."""

    @staticmethod
    def determine_request_flow(
        show_more_details: Optional[Dict[str, Any]],
        filtered_question: bool,
        selected_filters: Optional[Dict[str, Any]],
    ) -> str:
        """
        Determine which execution flow (A, B, or C) to use based on request characteristics.
        
        Args:
            show_more_details: Optional dict with pagination request data
            filtered_question: Boolean indicating if query has metadata filters
            selected_filters: Optional dict of selected filter values
            
        Returns:
            Flow identifier: 'A' (standard), 'B' (pagination), or 'C' (pre-filtered)
        """
        if show_more_details is not None:
            logging.info("Request routing: Flow B (Pagination detected)")
            return 'B'
        elif filtered_question and selected_filters:
            logging.info("Request routing: Flow C (Pre-filtered query detected)")
            return 'C'
        else:
            logging.info("Request routing: Flow A (Standard retrieval)")
            return 'A'

    @staticmethod
    def extract_show_more_parameters(
        show_more_details: Dict[str, Any],
        default_length: int,
        max_length: int,
    ) -> Tuple[int, str]:
        """
        Extract and validate pagination parameters from show_more_details.
        
        Args:
            show_more_details: Dict containing 'length' and 'question' keys
            default_length: Default number of results to fetch
            max_length: Maximum allowed results
            
        Returns:
            Tuple of (length, question) with validated values
        """
        try:
            length = show_more_details.get('length', default_length)
            question = show_more_details.get('question', '')
            
            # Validate length
            if not isinstance(length, int) or length < 1:
                logging.warning(f"Invalid length {length}, using default {default_length}")
                length = default_length
            
            length = min(length, max_length)
            
            if not question or not isinstance(question, str):
                logging.warning("No valid question found in show_more_details")
                question = ''
            
            logging.info(f"Pagination parameters: length={length}, question='{question}'")
            return length, question
            
        except Exception as e:
            logging.error(f"Error extracting pagination parameters: {e}")
            return default_length, ''

    @staticmethod
    def apply_metadata_filters(
        documents: List[Dict[str, Any]],
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Apply metadata filters to a list of documents.
        Filters out documents that don't match all provided filter criteria.
        
        Args:
            documents: List of document dictionaries
            filters: Dict of filter_key -> filter_value pairs
            
        Returns:
            Filtered list of documents
        """
        try:
            if not filters:
                logging.info("No filters to apply")
                return documents
            
            if not documents:
                logging.warning("No documents to filter")
                return []
            
            filtered_docs = []
            
            for doc in documents:
                matches_all = True
                
                for filter_key, filter_value in filters.items():
                    # Get filter value from doc metadata or root level
                    doc_value = doc.get('metadata', {}).get(filter_key) or doc.get(filter_key)
                    
                    # Compare values (case-insensitive for strings)
                    if isinstance(doc_value, str) and isinstance(filter_value, str):
                        if doc_value.lower() != filter_value.lower():
                            matches_all = False
                            break
                    elif doc_value != filter_value:
                        matches_all = False
                        break
                
                if matches_all:
                    filtered_docs.append(doc)
            
            logging.info(f"Applied filters: {len(documents)} -> {len(filtered_docs)} documents")
            return filtered_docs
            
        except Exception as e:
            logging.error(f"Error applying metadata filters: {e}", exc_info=True)
            return documents

    @staticmethod
    def manage_display_state(
        books: List[Dict[str, Any]],
        cited_isbns: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Update display state for books based on whether they were cited in the response.
        Marks cited books as displayed and increments their display_count.
        
        Args:
            books: List of book dictionaries
            cited_isbns: List of ISBNs that were cited in the LLM response
            
        Returns:
            Updated list of books with display state modified
        """
        try:
            for book in books:
                isbn = book.get('isbn')
                
                if isbn in cited_isbns:
                    book['is_displayed'] = True
                    book['display_count'] = book.get('display_count', 0) + 1
                    logging.debug(f"Marked {isbn} as displayed")
                else:
                    book['is_displayed'] = False
            
            logging.info(f"Updated display state for {len(books)} books")
            return books
            
        except Exception as e:
            logging.error(f"Error managing display state: {e}", exc_info=True)
            return books

    @staticmethod
    def extract_cited_isbns_from_response(response_text: str) -> List[str]:
        """
        Extract ISBN/book identifiers referenced in the LLM response.
        Looks for citation links or ISBN patterns in the text.
        
        Args:
            response_text: The LLM-generated response text
            
        Returns:
            List of ISBN strings found in the response
        """
        try:
            import re
            
            # Pattern for ISBN in citations: [text](url?isbn=ISBN)
            isbn_pattern = r'\[.*?\]\(.*?isbn=([\w\-]+).*?\)'
            isbns = re.findall(isbn_pattern, response_text, re.IGNORECASE)
            
            # Also look for standalone ISBN patterns
            isbn_pattern_standalone = r'\b([0-9]{10}|[0-9]{13}|[0-9]{4}-[0-9]{4}-[0-9]{4}[0-9X])\b'
            isbns.extend(re.findall(isbn_pattern_standalone, response_text))
            
            # Deduplicate
            isbns = list(set(isbns))
            logging.info(f"Extracted {len(isbns)} ISBNs from response")
            
            return isbns
            
        except Exception as e:
            logging.error(f"Error extracting cited ISBNs: {e}")
            return []

    @staticmethod
    def should_preserve_context_for_later_turns(
        flow_type: str,
        num_books_returned: int,
        total_available: int,
    ) -> bool:
        """
        Determine if session context should be preserved for future "Show More" requests.
        
        Args:
            flow_type: 'A', 'B', or 'C'
            num_books_returned: Number of books in current response
            total_available: Total books available in retrieval
            
        Returns:
            True if context should be persisted, False otherwise
        """
        # Preserve context for Flow A (fresh search) to enable pagination
        # Skip preservation for Flow B (already paginating) and Flow C (filtered view)
        if flow_type == 'A' and total_available > num_books_returned:
            logging.info("Context preservation enabled for future pagination")
            return True
        else:
            logging.info(f"Context preservation disabled (flow={flow_type})")
            return False

