import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from llm_studio_agents.utils.utils_agent_pubsub import send_streaming_response_to_pubsub
from book_finder_agent.book_finder_database_retrieval import DatabaseRetrievalUtils
from book_finder_agent.book_finder_citation_helpers import CitationUtils


class ResponseFinalizer:
    """
    Unified response assembly, LLM generation, and citation verification (A5/B1/C1).
    Handles streaming, concurrent citation verification, and session persistence.
    """

    @staticmethod
    def finalize_response(
        agent,
        flow_type: str,
        user_query: str,
        retrieved_books: List[Dict],
        session_id: str,
        total_retrieved_books: Optional[int],
        show_more_details: Optional[Dict],
        next_trace=None,
        trace=None,
    ) -> Tuple[str, List[Dict], List[Dict], bool]:
        """
        Finalize response: generate LLM output, verify citations, persist session state.
        Returns: (response_text, retrieved_books_formatted, citations, bypass_flag)
        """
        try:
            # Emit initial streaming update (thinking/processing)
            try:
                send_streaming_response_to_pubsub(
                    data=agent.data,
                    text="",
                    is_stream_end=False,
                    thinking_break=True,
                    header_message=f"Processing {flow_type} flow request...",
                    explainability_id=agent.data.get('explainability_id')
                )
            except Exception as e:
                logging.warning(f"Failed to send initial streaming update: {e}")
            
            # Step 1: Format context for LLM (A5/B1/C1)
            context_text = ResponseFinalizer._format_context_for_llm(
                retrieved_books, agent.config.max_chunks_per_book
            )
            
            if not context_text.strip():
                logging.warning("Empty context for LLM")
                return agent.config.fallback_response, [], [], not agent.config.smart_response_adjustment
            
            # Step 2: Skip LLM generation if flow is B or C (pagination/filtered), or if disabled
            if flow_type in ['B', 'C'] or not agent.config.generate_response_from_docs:
                logging.info(f"Flow {flow_type}: Skipping LLM generation")
                response_text = f"Retrieved {len(retrieved_books)} results."
                formatted_books = [ResponseFinalizer._format_book_for_output(b) for b in retrieved_books]
                
                # Persist session state only for Flow A
                if flow_type == 'A':
                    try:
                        DatabaseRetrievalUtils._upsert_retrieved_documents(
                            agent, session_id, user_query, retrieved_books,
                            next_trace=next_trace, trace=trace
                        )
                    except Exception as e:
                        logging.warning(f"Failed to persist session state: {e}")
                
                return response_text, formatted_books, [], not agent.config.smart_response_adjustment
            
            # Step 3: Generate LLM response (A5)
            llm_response = ResponseFinalizer._generate_llm_response(
                agent, user_query, context_text, next_trace, trace
            )
            
            if not llm_response:
                logging.warning("Empty LLM response")
                return agent.config.fallback_response, [], [], not agent.config.smart_response_adjustment
            
            # Step 4: Emit streaming update with LLM response
            try:
                send_streaming_response_to_pubsub(
                    data=agent.data,
                    text=llm_response,
                    is_stream_end=False,
                    thinking_break=False,
                    header_message="Verifying citations...",
                    explainability_id=agent.data.get('explainability_id')
                )
            except Exception as e:
                logging.warning(f"Failed to send LLM response streaming update: {e}")
            
            # Step 5: Verify citations in parallel (A5)
            verified_response, citations = ResponseFinalizer._verify_citations_parallel(
                agent, llm_response, retrieved_books, next_trace, trace
            )
            
            # Step 6: Emit final streaming update
            try:
                send_streaming_response_to_pubsub(
                    data=agent.data,
                    text=verified_response,
                    is_stream_end=True,
                    thinking_break=False,
                    header_message="Response complete.",
                    explainability_id=agent.data.get('explainability_id')
                )
            except Exception as e:
                logging.warning(f"Failed to send final streaming update: {e}")
            
            # Step 7: Persist session state (A5)
            try:
                DatabaseRetrievalUtils._upsert_retrieved_documents(
                    agent, session_id, user_query, retrieved_books,
                    next_trace=next_trace, trace=trace
                )
            except Exception as e:
                logging.warning(f"Failed to persist session state: {e}")
            
            # Step 8: Format output books
            formatted_books = [ResponseFinalizer._format_book_for_output(b) for b in retrieved_books]
            
            logging.info(f"Response finalized with {len(citations)} citations")
            return verified_response, formatted_books, citations, not agent.config.smart_response_adjustment
            
        except Exception as e:
            logging.error(f"Error finalizing response: {e}", exc_info=True)
            return agent.config.fallback_response, [], [], not agent.config.smart_response_adjustment

    @staticmethod
    def _format_context_for_llm(
        retrieved_books: List[Dict],
        max_chunks_per_book: int = 3,
    ) -> str:
        """
        Format retrieved books and chunks into structured XML context for LLM.
        """
        context_parts = []
        
        for i, book in enumerate(retrieved_books, 1):
            isbn = book.get('isbn', 'UNKNOWN')
            title = book.get('title', 'Untitled')
            final_score = book.get('final_score', 0.0)
            
            # Get up to max_chunks_per_book chunks
            chunks = book.get('chunks', [])[:max_chunks_per_book]
            chunks_xml = '\n'.join([
                f"<chunk id='{c.get('chunk_id', 'unknown')}'>{c.get('text', '')}</chunk>"
                for c in chunks
            ])
            
            book_context = f"""
<book rank='{i}' score='{final_score:.4f}'>
  <isbn>{isbn}</isbn>
  <title>{title}</title>
  <retrieved_chunks>
{chunks_xml}
  </retrieved_chunks>
</book>
"""
            context_parts.append(book_context)
        
        return "\n".join(context_parts)

    @staticmethod
    def _generate_llm_response(
        agent,
        user_query: str,
        context: str,
        next_trace,
        trace,
    ) -> str:
        """
        Generate LLM response using gemini-2.0-flash-001 model.
        """
        try:
            system_prompt = f"""You are a helpful book recommendation assistant. 
Provide accurate, evidence-backed responses using only the provided book excerpts.
Always cite specific books and excerpts. If information is not available, say so.

Available Books Context:
{context}

Respond to the user's query using ONLY the provided context.
Format citations as [source: book_title, ISBN: isbn].
"""
            
            # Set LLM context and model
            agent.llm_config_tool.config.context = system_prompt
            agent.llm_config_tool.config.model = 'gemini-2.0-flash-001'
            
            # Call LLM
            response = agent.llm_config_tool.run(
                query=user_query,
                next_trace=next_trace,
                trace=trace,
            )
            
            if not response:
                logging.warning("LLM returned empty response")
                return ""
            
            return response
            
        except Exception as e:
            logging.error(f"Error generating LLM response: {e}", exc_info=True)
            return ""

    @staticmethod
    def _verify_citations_parallel(
        agent,
        llm_response: str,
        retrieved_books: List[Dict],
        next_trace=None,
        trace=None,
    ) -> Tuple[str, List[Dict]]:
        """
        Extract citations from LLM response and verify them in parallel.
        Returns: (verified_response, citations_list)
        """
        try:
            # Extract citations from response
            citations = CitationUtils.extract_citations_from_response(llm_response)
            
            if not citations:
                logging.info("No citations found in response")
                return llm_response, []
            
            logging.info(f"Extracted {len(citations)} citations for verification")
            
            # Build source text map
            source_map = {}
            for book in retrieved_books:
                isbn = book.get('isbn')
                for chunk in book.get('chunks', []):
                    chunk_id = chunk.get('chunk_id')
                    source_map[chunk_id] = {
                        'isbn': isbn,
                        'text': chunk.get('text', ''),
                        'title': book.get('title', ''),
                    }
            
            # Verify citations in parallel
            verified_citations = []
            unverified_citation_indices = []
            
            max_workers = min(agent.config.max_workers_for_citation_generation, len(citations))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                
                for i, citation in enumerate(citations):
                    # Find source text
                    source_chunk_id = citation.get('source_chunk_id')
                    source_info = source_map.get(source_chunk_id)
                    
                    if source_info:
                        future = executor.submit(
                            ResponseFinalizer._verify_single_citation,
                            citation.get('cited_text', ''),
                            source_info['text'],
                        )
                        futures[future] = (i, citation, source_info)
                
                # Collect results
                for future in as_completed(futures):
                    idx, citation, source_info = futures[future]
                    try:
                        is_verified = future.result(timeout=10)
                        citation['verified'] = is_verified
                        citation['source_isbn'] = source_info['isbn']
                        citation['source_title'] = source_info['title']
                        
                        if is_verified:
                            verified_citations.append(citation)
                        else:
                            unverified_citation_indices.append(idx)
                    except Exception as e:
                        logging.warning(f"Citation verification failed for citation {idx}: {e}")
                        unverified_citation_indices.append(idx)
            
            # Strip unverified citations from response
            verified_response = ResponseFinalizer._strip_unverified_citations(
                llm_response, unverified_citation_indices
            )
            
            logging.info(f"Verified {len(verified_citations)} out of {len(citations)} citations")
            return verified_response, verified_citations
            
        except Exception as e:
            logging.error(f"Error verifying citations: {e}", exc_info=True)
            return llm_response, []

    @staticmethod
    def _verify_single_citation(cited_text: str, source_text: str) -> bool:
        """
        Verify a citation by checking if cited_text appears verbatim in source_text.
        """
        try:
            # Normalize whitespace for comparison
            cited_normalized = ' '.join(cited_text.split())
            source_normalized = ' '.join(source_text.split())
            
            # Check for verbatim match
            return cited_normalized.lower() in source_normalized.lower()
        except Exception as e:
            logging.warning(f"Error verifying single citation: {e}")
            return False

    @staticmethod
    def _strip_unverified_citations(response: str, unverified_indices: List[int]) -> str:
        """
        Remove citation links for unverified citations from response.
        """
        try:
            # Find all citation patterns in response
            # Pattern: [source: ..., ISBN: ...] or similar
            citation_pattern = r'\[source:[^\]]+\]|\[ISBN:[^\]]+\]'
            citations = list(re.finditer(citation_pattern, response))
            
            # Remove unverified citations
            if not unverified_indices or not citations:
                return response
            
            # Sort indices in reverse to avoid offset issues
            unverified_indices_sorted = sorted(unverified_indices, reverse=True)
            
            for idx in unverified_indices_sorted:
                if idx < len(citations):
                    citation_match = citations[idx]
                    response = response[:citation_match.start()] + response[citation_match.end():]
            
            return response
        except Exception as e:
            logging.warning(f"Error stripping unverified citations: {e}")
            return response

    @staticmethod
    def _format_book_for_output(book: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a book dictionary for inclusion in output response.
        """
        return {
            'isbn': book.get('isbn'),
            'title': book.get('title'),
            'final_score': book.get('final_score', 0.0),
            'chunks': [
                {
                    'chunk_id': c.get('chunk_id'),
                    'text': c.get('text'),
                    'similarity_score': c.get('similarity_score', 0.0),
                }
                for c in book.get('chunks', [])
            ],
            'scores': {
                'semantic_similarity': book.get('semantic_similarity_score', 0.0),
                'document_overlap': book.get('document_overlap_score', 0.0),
                'keyword_frequency': book.get('keyword_score', 0.0),
            }
        }

