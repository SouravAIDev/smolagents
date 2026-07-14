import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from llm_studio_agents.utils.utils_agent_pubsub import send_streaming_response_to_pubsub


class BookFinderLLMOrchestration:
    """Manages LLM invocation and response generation for BookFinderAgent."""

    @staticmethod
    def prepare_context_block(
        ranked_books: List[Dict[str, Any]],
        user_query: str,
        config: Any,
    ) -> str:
        """
        Prepare an XML-formatted context block from top-ranked books.
        
        Args:
            ranked_books: Books sorted by final_score (descending)
            user_query: Original user query
            config: BookFinderAgentSetup configuration object
            
        Returns:
            XML-formatted context string ready for LLM injection
        """
        try:
            if not ranked_books:
                logging.warning("No ranked books provided for context preparation")
                return ""
            
            # Limit to books_per_result
            max_books = max(1, int(config.books_per_result))
            books_to_include = ranked_books[:max_books]
            
            context_lines = [
                "<context>",
                "<retrieved_books>",
            ]
            
            for idx, book in enumerate(books_to_include, 1):
                isbn = book.get("isbn", "N/A")
                title = book.get("title", "Unknown Title")
                authors = book.get("authors", [])
                if isinstance(authors, list):
                    author_str = ", ".join(authors) if authors else "Unknown Author"
                else:
                    author_str = str(authors)
                    
                genres = book.get("genres", [])
                if isinstance(genres, list):
                    genre_str = ", ".join(genres) if genres else "Unknown Genre"
                else:
                    genre_str = str(genres)
                    
                summary = book.get("summary", "")
                final_score = book.get("final_score", 0.0)
                
                # Retrieve supporting chunks (limit to max_chunks_to_use)
                chunks = book.get("supporting_chunks", [])
                max_chunks = max(1, int(config.max_chunks_to_use))
                chunks_to_include = chunks[:max_chunks]
                
                context_lines.append(
                    f"  <book index=\"{idx}\" isbn=\"{isbn}\" relevance_score=\"{final_score:.2f}\">"
                )
                context_lines.append(f"    <title>{BookFinderLLMOrchestration._escape_xml(title)}</title>")
                context_lines.append(f"    <authors>{BookFinderLLMOrchestration._escape_xml(author_str)}</authors>")
                context_lines.append(f"    <genres>{BookFinderLLMOrchestration._escape_xml(genre_str)}</genres>")
                context_lines.append(f"    <summary>{BookFinderLLMOrchestration._escape_xml(summary)}</summary>")
                
                if chunks_to_include:
                    context_lines.append("    <retrieved_chunks>")
                    for chunk_idx, chunk in enumerate(chunks_to_include, 1):
                        chunk_text = chunk.get("chunk_text", "")
                        chunk_id = chunk.get("chunk_id", "unknown")
                        similarity = chunk.get("similarity_score", 0.0)
                        context_lines.append(
                            f"      <chunk id=\"{chunk_idx}\" chunk_id=\"{chunk_id}\" similarity=\"{similarity:.2f}\">"
                        )
                        context_lines.append(
                            f"        {BookFinderLLMOrchestration._escape_xml(chunk_text)}"
                        )
                        context_lines.append("      </chunk>")
                    context_lines.append("    </retrieved_chunks>")
                
                context_lines.append("  </book>")
            
            context_lines.append("</retrieved_books>")
            context_lines.append("</context>")
            
            return "\n".join(context_lines)
        except Exception as e:
            logging.error(f"Error preparing context block: {e}", exc_info=True)
            return ""

    @staticmethod
    def generate_response(
        context: str,
        user_query: str,
        config: Any,
        llm_tool: Any,
        data: Optional[Dict] = None,
        next_trace: Optional[Dict] = None,
        trace: Optional[Dict] = None,
    ) -> str:
        """
        Generate LLM response using prepared context.
        
        Args:
            context: XML-formatted context block from prepare_context_block()
            user_query: Original user query
            config: BookFinderAgentSetup configuration
            llm_tool: LLMConfigurationTool instance
            data: Optional request data for streaming
            next_trace: Optional trace handler
            trace: Optional trace handler
            
        Returns:
            Generated response text with markdown citations, or fallback_response on failure
        """
        try:
            if not context or not context.strip():
                logging.warning("Empty context provided to LLM generation")
                return config.fallback_response
            
            # Construct prompt with context
            prompt = BookFinderLLMOrchestration._build_prompt(
                user_query=user_query,
                context=context,
                config=config
            )
            
            logging.info(f"Generated LLM prompt (length: {len(prompt)})")
            
            # Configure LLM tool for streaming
            llm_tool.config.context = prompt
            
            # Send initial streaming heartbeat
            try:
                if data:
                    send_streaming_response_to_pubsub(
                        data=data,
                        text="",
                        is_stream_end=False,
                        thinking_break=False,
                        header_message="Generating response...",
                        explainability_id=data.get("explainability_id"),
                    )
            except Exception as e:
                logging.warning(f"Error sending initial streaming heartbeat: {e}")
            
            # Invoke LLM
            response = llm_tool.run(
                query=user_query,
                next_trace=next_trace,
                trace=trace,
            )
            
            if not response or not str(response).strip():
                logging.warning("LLM returned empty response")
                return config.fallback_response
            
            response_text = str(response).strip()
            logging.info(f"LLM response generated (length: {len(response_text)})")
            
            return response_text
        except Exception as e:
            logging.error(f"Error generating LLM response: {e}", exc_info=True)
            return config.fallback_response

    @staticmethod
    def _build_prompt(
        user_query: str,
        context: str,
        config: Any,
    ) -> str:
        """
        Construct the prompt for LLM invocation.
        
        Args:
            user_query: User's original question
            context: XML-formatted book context
            config: Configuration object
            
        Returns:
            Formatted prompt string
        """
        prompt_template = getattr(config, "prompt_template", None)
        
        if prompt_template:
            # Use custom template if provided
            try:
                prompt = prompt_template.format(
                    user_query=user_query,
                    context=context
                )
            except KeyError:
                # Fallback if template keys don't match
                prompt = f"{prompt_template}\n\nUser Query: {user_query}\n\n{context}"
        else:
            # Default prompt structure
            prompt = f"""You are a helpful book discovery assistant. Based on the following retrieved books and their supporting excerpts, provide a comprehensive answer to the user's query.

User Query: {user_query}

Retrieved Books and Supporting Excerpts:
{context}

Instructions:
1. Synthesize a response based on the retrieved book information.
2. Include citations using markdown format: [quoted text](URL_with_metadata)
3. Ensure all citations are verbatim from the source material.
4. If no relevant information is found, clearly state that.
5. Maintain a conversational, helpful tone.

Response:"""
        
        return prompt

    @staticmethod
    def _escape_xml(text: str) -> str:
        """
        Escape XML special characters in text.
        
        Args:
            text: Text to escape
            
        Returns:
            XML-escaped text
        """
        if not text:
            return ""
        
        text = str(text)
        replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&apos;",
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text

