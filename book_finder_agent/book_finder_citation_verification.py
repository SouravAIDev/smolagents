import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Pattern
from concurrent.futures import ThreadPoolExecutor, as_completed


class CitationVerificationEngine:
    """Manages citation extraction and parallel verification for BookFinderAgent."""
    
    # Regex patterns for citation extraction
    CITATION_PATTERN: Pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    ISBN_PATTERN: Pattern = re.compile(r'\b(?:\d{10}|\d{13})\b')
    UUID_PATTERN: Pattern = re.compile(r'[a-fA-F0-9\-]{36}')
    
    @staticmethod
    def extract_citations_from_response(
        response_text: str,
    ) -> List[Tuple[str, str, int]]:
        """
        Extract markdown-formatted citations from LLM response.
        
        Args:
            response_text: LLM-generated response text
            
        Returns:
            List of tuples: (citation_text, url, match_index)
        """
        citations = []
        
        if not response_text:
            logging.warning("Empty response text provided for citation extraction")
            return citations
        
        try:
            matches = list(CitationVerificationEngine.CITATION_PATTERN.finditer(response_text))
            logging.info(f"Extracted {len(matches)} potential citations from response")
            
            for idx, match in enumerate(matches):
                citation_text = match.group(1).strip()
                citation_url = match.group(2).strip()
                
                if citation_text and citation_url:
                    citations.append((citation_text, citation_url, idx))
            
            return citations
        except Exception as e:
            logging.error(f"Error extracting citations: {e}", exc_info=True)
            return []
    
    @staticmethod
    def parse_citation_metadata(citation_url: str) -> Dict[str, Any]:
        """
        Parse citation URL to extract metadata.
        
        Args:
            citation_url: URL from markdown citation
            
        Returns:
            Dictionary with extracted metadata (isbn, chunk_id, citation_source, etc.)
        """
        metadata = {
            "isbn": None,
            "chunk_id": None,
            "citation_source": "supporting_chunks",
            "associated_id": None,
        }
        
        try:
            # Extract ISBN (10 or 13 digits)
            isbn_match = CitationVerificationEngine.ISBN_PATTERN.search(citation_url)
            if isbn_match:
                metadata["isbn"] = isbn_match.group(0)
            
            # Extract chunk_id or UUID
            uuid_match = CitationVerificationEngine.UUID_PATTERN.search(citation_url)
            if uuid_match:
                metadata["chunk_id"] = uuid_match.group(0)
                metadata["associated_id"] = uuid_match.group(0)
            
            # Extract query parameters
            if "?" in citation_url:
                query_string = citation_url.split("?")[1]
                for param in query_string.split("&"):
                    if "=" in param:
                        key, value = param.split("=", 1)
                        key = key.strip().lower()
                        
                        if key in ["citation_source", "citationsource"]:
                            metadata["citation_source"] = value.strip()
            
            return metadata
        except Exception as e:
            logging.warning(f"Error parsing citation metadata: {e}")
            return metadata
    
    @staticmethod
    def verify_citation(
        citation_text: str,
        source_texts: List[str],
        strip_whitespace: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify that citation text exists verbatim in source material.
        
        Args:
            citation_text: Text quoted in the citation
            source_texts: List of potential source texts to search in
            strip_whitespace: Whether to strip leading/trailing whitespace for matching
            
        Returns:
            Tuple: (is_verified, matching_source_text)
        """
        if not citation_text or not source_texts:
            return False, None
        
        try:
            # First attempt: exact match
            for source in source_texts:
                if not source:
                    continue
                    
                if citation_text in source:
                    return True, source
            
            # Second attempt: whitespace-normalized match
            if strip_whitespace:
                normalized_citation = " ".join(citation_text.split())
                for source in source_texts:
                    if not source:
                        continue
                    
                    normalized_source = " ".join(source.split())
                    if normalized_citation in normalized_source:
                        return True, source
            
            return False, None
        except Exception as e:
            logging.error(f"Error verifying citation: {e}")
            return False, None
    
    @staticmethod
    def verify_citations_parallel(
        citations: List[Tuple[str, str, int]],
        ranked_books: List[Dict[str, Any]],
        config: Any,
        citation_tool: Optional[Any] = None,
        max_workers: int = 10,
    ) -> Tuple[str, List[Tuple[int, bool, Optional[str]]]]:
        """
        Verify citations in parallel using ThreadPoolExecutor.
        
        Args:
            citations: List of (citation_text, url, index) tuples
            ranked_books: List of ranked books with source material
            config: BookFinderAgentSetup configuration
            citation_tool: Optional CitationTool instance for dedicated verification
            max_workers: Maximum number of parallel workers
            
        Returns:
            Tuple: (verification_status_string, verification_results)
        """
        if not citations:
            return "No citations to verify", []
        
        verification_results = []
        
        try:
            # Build a map of chunk_ids to source texts from ranked books
            source_map = CitationVerificationEngine._build_source_map(ranked_books)
            
            logging.info(
                f"Starting parallel citation verification with {len(citations)} citations "
                f"using {max_workers} workers"
            )
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                
                for citation_text, citation_url, idx in citations:
                    # Submit verification task
                    future = executor.submit(
                        CitationVerificationEngine._verify_single_citation,
                        citation_text=citation_text,
                        citation_url=citation_url,
                        citation_idx=idx,
                        source_map=source_map,
                        ranked_books=ranked_books,
                        citation_tool=citation_tool,
                    )
                    futures[future] = idx
                
                # Collect results as they complete
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        verification_results.append(result)
                    except Exception as e:
                        idx = futures[future]
                        logging.error(
                            f"Error verifying citation at index {idx}: {e}",
                            exc_info=True,
                        )
                        verification_results.append((idx, False, None))
            
            # Sort results by original citation index
            verification_results.sort(key=lambda x: x[0])
            
            verified_count = sum(1 for _, is_verified, _ in verification_results if is_verified)
            total_count = len(verification_results)
            
            status = f"Verified {verified_count}/{total_count} citations"
            logging.info(status)
            
            return status, verification_results
        except Exception as e:
            logging.error(f"Error in parallel citation verification: {e}", exc_info=True)
            return "Citation verification failed", []
    
    @staticmethod
    def _verify_single_citation(
        citation_text: str,
        citation_url: str,
        citation_idx: int,
        source_map: Dict[str, List[str]],
        ranked_books: List[Dict[str, Any]],
        citation_tool: Optional[Any] = None,
    ) -> Tuple[int, bool, Optional[str]]:
        """
        Verify a single citation with retry logic.
        
        Args:
            citation_text: Text to verify
            citation_url: Citation URL
            citation_idx: Index of citation in original response
            source_map: Pre-built map of sources
            ranked_books: List of ranked books
            citation_tool: Optional dedicated citation tool
            
        Returns:
            Tuple: (citation_idx, is_verified, matching_source)
        """
        try:
            metadata = CitationVerificationEngine.parse_citation_metadata(citation_url)
            
            # Attempt 1: Direct verification
            if metadata["chunk_id"]:
                sources = source_map.get(metadata["chunk_id"], [])
                is_verified, matching_source = CitationVerificationEngine.verify_citation(
                    citation_text, sources
                )
                if is_verified:
                    return citation_idx, True, matching_source
            
            # Attempt 2: Search across all sources if chunk_id didn't work
            all_sources = []
            for sources_list in source_map.values():
                all_sources.extend(sources_list)
            
            if all_sources:
                is_verified, matching_source = CitationVerificationEngine.verify_citation(
                    citation_text, all_sources
                )
                if is_verified:
                    return citation_idx, True, matching_source
            
            # Attempt 3: Try searching all book summaries and content
            fallback_sources = []
            for book in ranked_books:
                if book.get("summary"):
                    fallback_sources.append(book["summary"])
            
            if fallback_sources:
                is_verified, matching_source = CitationVerificationEngine.verify_citation(
                    citation_text, fallback_sources
                )
                if is_verified:
                    return citation_idx, True, matching_source
            
            # All verification attempts failed
            logging.warning(
                f"Citation at index {citation_idx} failed verification: \"{citation_text[:50]}...\""
            )
            return citation_idx, False, None
        except Exception as e:
            logging.error(f"Error verifying single citation at index {citation_idx}: {e}")
            return citation_idx, False, None
    
    @staticmethod
    def _build_source_map(ranked_books: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Build a map of chunk_ids to source texts from ranked books.
        
        Args:
            ranked_books: List of ranked books
            
        Returns:
            Dictionary mapping chunk_id to list of source texts
        """
        source_map = {}
        
        try:
            for book in ranked_books:
                chunks = book.get("supporting_chunks", [])
                
                if isinstance(chunks, list):
                    for chunk in chunks:
                        if isinstance(chunk, dict):
                            chunk_id = chunk.get("chunk_id")
                            chunk_text = chunk.get("chunk_text")
                            
                            if chunk_id and chunk_text:
                                if chunk_id not in source_map:
                                    source_map[chunk_id] = []
                                source_map[chunk_id].append(str(chunk_text))
            
            logging.info(f"Built source map with {len(source_map)} unique chunks")
            return source_map
        except Exception as e:
            logging.error(f"Error building source map: {e}")
            return {}
    
    @staticmethod
    def strip_unverified_citations(
        response_text: str,
        verification_results: List[Tuple[int, bool, Optional[str]]],
    ) -> str:
        """
        Strip markdown citation links for unverified citations.
        
        Args:
            response_text: Original LLM response
            verification_results: List of (idx, is_verified, source) tuples
            
        Returns:
            Response with unverified citations stripped
        """
        if not verification_results:
            return response_text
        
        try:
            # Build set of indices that failed verification
            failed_indices = {idx for idx, is_verified, _ in verification_results if not is_verified}
            
            if not failed_indices:
                return response_text  # All citations verified
            
            # Find and replace unverified citations
            matches = list(CitationVerificationEngine.CITATION_PATTERN.finditer(response_text))
            
            # Process matches in reverse order to maintain string indices
            result = response_text
            for idx, match in enumerate(reversed(matches)):
                if idx in failed_indices:
                    # Extract just the citation text, removing the markdown link
                    citation_text = match.group(1)
                    
                    # Replace [text](url) with just text
                    result = result[:match.start()] + citation_text + result[match.end():]
            
            logging.info(f"Stripped {len(failed_indices)} unverified citations from response")
            return result
        except Exception as e:
            logging.error(f"Error stripping unverified citations: {e}")
            return response_text

