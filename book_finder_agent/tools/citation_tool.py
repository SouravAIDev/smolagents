"""Citation Tool for extracting and verifying citations from LLM responses.

This tool extracts citations in markdown format from LLM-generated text,
verifies each citation against provided source texts using parallel processing,
and returns structured verification results.
"""

import logging
import re
import string
from typing import Optional, List, Dict, Any, Annotated, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from pydantic import Field

from llm_studio_agents.AgentBase import AgentSetupBase


# Regex pattern to extract markdown citations: [text](url)
CITATION_PATTERN = r'\[([^\]]+)\]\(([^)]+)\)'


class CitationToolSetup(AgentSetupBase):
    """Configuration schema for CitationTool."""
    
    max_workers: Optional[int] = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of parallel workers for citation verification.",
        title="Max Workers",
    )
    retry_attempts: Optional[int] = Field(
        default=1,
        ge=0,
        le=3,
        description="Number of retry attempts for failed verification checks.",
        title="Retry Attempts",
    )
    batch_size: Optional[int] = Field(
        default=10,
        ge=1,
        le=100,
        description="Batch size for processing citations.",
        title="Batch Size",
    )
    timeout_seconds: Optional[int] = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout in seconds for individual citation verification.",
        title="Timeout Seconds",
    )


class CitationTool:
    """Tool for extracting and verifying citations from LLM responses.
    
    This tool extracts markdown-style citations [text](url) from LLM output,
    verifies each against provided source texts in parallel, implements
    retry logic with whitespace stripping, and returns structured results.
    """
    
    CONFIG_CLASS = CitationToolSetup
    
    def __init__(self):
        """Initialize the tool."""
        self.config = None
    
    def setup(self, config: dict, data: Optional[dict] = None) -> dict:
        """Initialize tool configuration.
        
        Args:
            config: Configuration dictionary with citation settings
            data: Optional shared request data dictionary
            
        Returns:
            Empty dict on success
        """
        try:
            if isinstance(config, dict):
                self.config = CitationToolSetup(**config)
            else:
                self.config = config
            
            logging.info(f"Initialized CitationTool with max_workers={self.config.max_workers}")
            return {}
            
        except Exception as e:
            logging.error(f"Error in CitationTool.setup: {e}", exc_info=True)
            return {}
    
    def run(
        self,
        response_text: Annotated[str, "LLM response text containing citations."],
        source_texts: Annotated[Optional[List[Dict[str, str]]], "List of dicts with 'text' and optionally 'source_id' keys."] = None,
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None,
    ) -> List[Dict[str, Any]]:
        """Extract and verify citations from LLM response.
        
        Args:
            response_text: Text containing markdown-style citations [text](url)
            source_texts: List of source text dicts with keys 'text' and optionally 'source_id'
            next_trace: Optional trace dictionary for nested observability
            trace: Optional trace dictionary for nested observability
            
        Returns:
            List of citation dicts with keys: citation_text, source_url, verified, confidence, error
        """
        if not response_text or not isinstance(response_text, str):
            logging.warning("CitationTool.run: Invalid response_text")
            return []
        
        if not source_texts:
            logging.warning("CitationTool.run: No source texts provided for verification")
            return []
        
        try:
            # Extract citations from response
            citations = self._extract_citations(response_text)
            
            if not citations:
                logging.info("CitationTool.run: No citations found in response")
                return []
            
            logging.info(f"Extracted {len(citations)} citations for verification")
            
            # Build source text map
            source_map = self._build_source_map(source_texts)
            
            # Verify citations in parallel
            verified_citations = self._verify_citations_parallel(
                citations,
                source_map,
                source_texts
            )
            
            return verified_citations
            
        except Exception as e:
            logging.error(f"Error in CitationTool.run: {e}", exc_info=True)
            return []
    
    def _extract_citations(self, response_text: str) -> List[Dict[str, str]]:
        """Extract markdown citations from text.
        
        Args:
            response_text: Text containing markdown citations [text](url)
            
        Returns:
            List of dicts with keys: citation_text, source_url
        """
        citations = []
        
        try:
            matches = re.finditer(CITATION_PATTERN, response_text)
            
            for i, match in enumerate(matches):
                citation_text = match.group(1).strip()
                source_url = match.group(2).strip()
                
                if citation_text and source_url:
                    citations.append({
                        'citation_text': citation_text,
                        'source_url': source_url,
                        'position': match.start(),
                    })
            
            logging.debug(f"Extracted {len(citations)} citations from response")
            return citations
            
        except Exception as e:
            logging.error(f"Error extracting citations: {e}", exc_info=True)
            return []
    
    def _build_source_map(self, source_texts: List[Dict[str, str]]) -> Dict[str, str]:
        """Build a map of source IDs to source text content.
        
        Args:
            source_texts: List of dicts with 'text' and optionally 'source_id' keys
            
        Returns:
            Dict mapping source_id to text content
        """
        source_map = {}
        
        try:
            for i, item in enumerate(source_texts):
                if isinstance(item, dict) and 'text' in item:
                    source_id = item.get('source_id', f'source_{i}')
                    source_map[source_id] = item['text']
                else:
                    logging.warning(f"Invalid source_text item at index {i}: missing 'text' key")
            
            logging.debug(f"Built source map with {len(source_map)} entries")
            return source_map
            
        except Exception as e:
            logging.error(f"Error building source map: {e}", exc_info=True)
            return {}
    
    def _verify_citations_parallel(
        self,
        citations: List[Dict[str, str]],
        source_map: Dict[str, str],
        source_texts: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Verify citations in parallel using ThreadPoolExecutor.
        
        Args:
            citations: List of extracted citations
            source_map: Map of source IDs to source text
            source_texts: Original source texts list
            
        Returns:
            List of citation dicts with verification status
        """
        verified_citations = []
        
        try:
            max_workers = min(self.config.max_workers, len(citations)) if citations else 1
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                
                for i, citation in enumerate(citations):
                    # Build combined source text for verification
                    combined_source = ' '.join([item.get('text', '') for item in source_texts])
                    
                    future = executor.submit(
                        self._verify_single_citation,
                        citation,
                        combined_source
                    )
                    futures[future] = (i, citation)
                
                # Collect results as they complete
                for future in as_completed(futures, timeout=self.config.timeout_seconds):
                    idx, original_citation = futures[future]
                    
                    try:
                        result = future.result(timeout=self.config.timeout_seconds)
                        verified_citations.append(result)
                    except TimeoutError:
                        logging.warning(f"Citation verification timeout for citation {idx}")
                        verified_citations.append({
                            'citation_text': original_citation.get('citation_text', ''),
                            'source_url': original_citation.get('source_url', ''),
                            'verified': False,
                            'confidence': 0.0,
                            'error': 'Verification timeout'
                        })
                    except Exception as e:
                        logging.warning(f"Error verifying citation {idx}: {e}")
                        verified_citations.append({
                            'citation_text': original_citation.get('citation_text', ''),
                            'source_url': original_citation.get('source_url', ''),
                            'verified': False,
                            'confidence': 0.0,
                            'error': str(e)
                        })
            
            # Sort by original position to maintain order
            verified_citations = sorted(
                verified_citations,
                key=lambda x: citations[next(i for i, c in enumerate(citations) if c.get('citation_text') == x.get('citation_text'))].get('position', 0)
            )
            
            logging.info(f"Verified {sum(1 for c in verified_citations if c.get('verified'))} of {len(verified_citations)} citations")
            return verified_citations
            
        except Exception as e:
            logging.error(f"Error verifying citations in parallel: {e}", exc_info=True)
            return []
    
    def _verify_single_citation(
        self,
        citation: Dict[str, str],
        source_text: str
    ) -> Dict[str, Any]:
        """Verify a single citation against source text.
        
        Args:
            citation: Dict with citation_text and source_url
            source_text: Full source text to verify against
            
        Returns:
            Dict with verification result
        """
        citation_text = citation.get('citation_text', '').strip()
        source_url = citation.get('source_url', '').strip()
        
        if not citation_text or not source_text:
            return {
                'citation_text': citation_text,
                'source_url': source_url,
                'verified': False,
                'confidence': 0.0,
                'error': 'Empty citation or source text'
            }
        
        # First attempt: exact substring match
        is_verified, confidence = self._check_substring_match(citation_text, source_text)
        
        if is_verified:
            return {
                'citation_text': citation_text,
                'source_url': source_url,
                'verified': True,
                'confidence': confidence,
                'error': None
            }
        
        # Second attempt: with whitespace/punctuation stripping (retry logic)
        if self.config.retry_attempts > 0:
            stripped_citation = self._strip_punctuation(citation_text)
            is_verified, confidence = self._check_substring_match(stripped_citation, source_text, allow_stripped=True)
            
            if is_verified:
                return {
                    'citation_text': citation_text,
                    'source_url': source_url,
                    'verified': True,
                    'confidence': confidence,
                    'error': None
                }
        
        # If still not verified
        return {
            'citation_text': citation_text,
            'source_url': source_url,
            'verified': False,
            'confidence': 0.0,
            'error': 'Citation not found in source text'
        }
    
    def _check_substring_match(
        self,
        citation_text: str,
        source_text: str,
        allow_stripped: bool = False
    ) -> Tuple[bool, float]:
        """Check if citation text appears as substring in source.
        
        Args:
            citation_text: Text to find
            source_text: Text to search in
            allow_stripped: If True, allow partial matches after stripping punctuation
            
        Returns:
            Tuple of (is_verified: bool, confidence: float)
        """
        try:
            # Exact match
            if citation_text.lower() in source_text.lower():
                return (True, 1.0)
            
            # Stripped match (if allowed)
            if allow_stripped:
                stripped_citation = self._strip_punctuation(citation_text).lower()
                stripped_source = self._strip_punctuation(source_text).lower()
                
                if stripped_citation and stripped_citation in stripped_source:
                    return (True, 0.85)  # Slightly lower confidence for stripped match
            
            return (False, 0.0)
            
        except Exception as e:
            logging.debug(f"Error checking substring match: {e}")
            return (False, 0.0)
    
    def _strip_punctuation(self, text: str) -> str:
        """Remove punctuation and normalize whitespace.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        try:
            # Remove punctuation
            text = text.translate(str.maketrans('', '', string.punctuation))
            # Normalize whitespace
            text = ' '.join(text.split())
            return text
        except Exception as e:
            logging.debug(f"Error stripping punctuation: {e}")
            return text

