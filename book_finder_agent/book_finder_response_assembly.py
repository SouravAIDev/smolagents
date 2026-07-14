import logging
from typing import Dict, List, Any, Optional, Tuple

from llm_studio_agents.utils.utils import citation_generator


class ResponseAssembly:
    """Assembles final response tuple for BookFinderAgent."""
    
    @staticmethod
    def assemble_response_tuple(
        response_text: str,
        ranked_books: List[Dict[str, Any]],
        verification_results: List[Tuple[int, bool, Optional[str]]],
        config: Any,
        agent_name: str = "BookFinderAgent",
        bypass_orchestrator_response: bool = False,
    ) -> Tuple[str, List[Dict], List[Dict], bool]:
        """
        Assemble the final response tuple meeting LLM Studio contract.
        
        Args:
            response_text: LLM-generated response with citations
            ranked_books: List of ranked books used for context
            verification_results: Citation verification results
            config: BookFinderAgentSetup configuration
            agent_name: Name of the agent for citations
            bypass_orchestrator_response: Flag for downstream post-processing
            
        Returns:
            4-tuple: (response_text, retrieved_books, citations, bypass_flag)
        """
        try:
            # Validate response text
            if not response_text or not str(response_text).strip():
                logging.warning("Empty response text in response assembly")
                response_text = config.fallback_response
            
            # Format retrieved books for return
            retrieved_books = ResponseAssembly._format_retrieved_books(ranked_books)
            
            # Generate citations from verification results
            citations = ResponseAssembly._generate_citations(
                ranked_books=ranked_books,
                verification_results=verification_results,
                agent_name=agent_name,
                config=config,
            )
            
            # Ensure citations is never None
            if not citations:
                citations = [
                    citation_generator(
                        agent_name=agent_name,
                        title="Book Finder Results",
                        url="",
                        description="Retrieved book recommendations",
                        metadata={},
                    )
                ]
            
            # Validate bypass flag
            bypass_flag = bool(bypass_orchestrator_response or not config.smart_response_adjustment)
            
            logging.info(
                f"Assembled response tuple: "
                f"response_length={len(response_text)}, "
                f"retrieved_books={len(retrieved_books)}, "
                f"citations={len(citations)}, "
                f"bypass_flag={bypass_flag}"
            )
            
            return response_text, retrieved_books, citations, bypass_flag
        except Exception as e:
            logging.error(f"Error assembling response tuple: {e}", exc_info=True)
            # Return safe fallback
            return (
                config.fallback_response,
                [],
                [],
                not config.smart_response_adjustment,
            )
    
    @staticmethod
    def _format_retrieved_books(
        ranked_books: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Format ranked books for client consumption.
        
        Args:
            ranked_books: List of ranked book dictionaries
            
        Returns:
            Formatted list suitable for client response
        """
        try:
            formatted_books = []
            
            for idx, book in enumerate(ranked_books, 1):
                formatted_book = {
                    "rank": idx,
                    "isbn": book.get("isbn", "N/A"),
                    "title": book.get("title", "Unknown Title"),
                    "authors": book.get("authors", []),
                    "genres": book.get("genres", []),
                    "summary": book.get("summary", ""),
                    "final_score": book.get("final_score", 0.0),
                    "chunk_count": len(book.get("supporting_chunks", [])),
                }
                
                formatted_books.append(formatted_book)
            
            return formatted_books
        except Exception as e:
            logging.error(f"Error formatting retrieved books: {e}")
            return []
    
    @staticmethod
    def _generate_citations(
        ranked_books: List[Dict[str, Any]],
        verification_results: List[Tuple[int, bool, Optional[str]]],
        agent_name: str,
        config: Any,
    ) -> List[Dict[str, Any]]:
        """
        Generate citation objects for all verified citations.
        
        Args:
            ranked_books: List of ranked books
            verification_results: Citation verification results
            agent_name: Name of the agent
            config: Configuration object
            
        Returns:
            List of citation objects
        """
        citations = []
        
        try:
            if not ranked_books:
                return citations
            
            # Create a primary citation for the set of retrieved books
            primary_citation = citation_generator(
                agent_name=agent_name,
                title="Book Recommendations",
                url="",
                description=f"Found {len(ranked_books)} book recommendations based on your query",
                metadata={
                    "book_count": len(ranked_books),
                    "verified_citations": sum(1 for _, is_verified, _ in verification_results if is_verified),
                    "total_citations": len(verification_results),
                },
            )
            citations.append(primary_citation)
            
            # Create citations for each ranked book
            for book in ranked_books[:max(1, int(config.books_per_result))]:
                isbn = book.get("isbn", "unknown")
                title = book.get("title", "Unknown Title")
                summary = book.get("summary", "")
                final_score = book.get("final_score", 0.0)
                
                book_citation = citation_generator(
                    agent_name=agent_name,
                    title=title,
                    url=f"book://{isbn}",
                    description=f"Relevance Score: {final_score:.1%}. {summary[:200]}...",
                    metadata={
                        "isbn": isbn,
                        "relevance_score": final_score,
                        "chunk_count": len(book.get("supporting_chunks", [])),
                    },
                )
                citations.append(book_citation)
            
            logging.info(f"Generated {len(citations)} citations")
            return citations
        except Exception as e:
            logging.error(f"Error generating citations: {e}", exc_info=True)
            return []
    
    @staticmethod
    def validate_response_tuple(
        response_tuple: Tuple[str, List, List, bool],
    ) -> bool:
        """
        Validate response tuple meets contract requirements.
        
        Args:
            response_tuple: The 4-tuple to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            if not isinstance(response_tuple, tuple) or len(response_tuple) != 4:
                logging.error(
                    f"Invalid response tuple: expected 4-tuple, got {type(response_tuple)} with length {len(response_tuple) if isinstance(response_tuple, tuple) else 'N/A'}"
                )
                return False
            
            response_text, retrieved_books, citations, bypass_flag = response_tuple
            
            # Validate each component
            if not isinstance(response_text, str):
                logging.error(f"Invalid response_text type: {type(response_text)}")
                return False
            
            if not isinstance(retrieved_books, list):
                logging.error(f"Invalid retrieved_books type: {type(retrieved_books)}")
                return False
            
            if not isinstance(citations, list):
                logging.error(f"Invalid citations type: {type(citations)}")
                return False
            
            if not isinstance(bypass_flag, bool):
                logging.error(f"Invalid bypass_flag type: {type(bypass_flag)}")
                return False
            
            logging.info("Response tuple validation passed")
            return True
        except Exception as e:
            logging.error(f"Error validating response tuple: {e}")
            return False

