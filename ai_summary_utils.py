import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


class AIEmbeddingUtils:
    """Embedding generation and pgvector similarity search utilities for BookFinderAgent."""

    def generate_embedding(
        self,
        text: str,
        trace=None,
        next_trace=None
    ) -> Optional[List[float]]:
        """
        Generate embedding vector for input text using semantic similarity tool.
        
        Args:
            text (str): The text to generate an embedding for
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            list: Embedding vector of configured dimensions or None on error
        """
        try:
            if not text or not isinstance(text, str):
                logging.warning("Invalid text input for embedding generation")
                return None
            
            # Use semantic similarity tool to generate embedding
            embedding = self.semantic_similarity_tool.run(
                text=text.strip(),
                next_trace=next_trace,
                trace=trace
            )
            
            if isinstance(embedding, list) and len(embedding) == self.config.embedding_dimensions:
                logging.debug(f"Generated embedding of dimension {len(embedding)}")
                return embedding
            else:
                logging.error(f"Invalid embedding returned: {type(embedding)} with dimension {len(embedding) if isinstance(embedding, list) else 'N/A'}")
                return None
            
        except Exception as e:
            logging.error(f"Error generating embedding: {e}", exc_info=True)
            return None


    def search_similar_books(
        self,
        query_embedding: List[float],
        table_name: str,
        embedding_column: str,
        limit: int = 10,
        similarity_threshold: float = 0.3,
        trace=None,
        next_trace=None
    ) -> List[Dict[str, Any]]:
        """
        Execute pgvector cosine similarity search to find similar books.
        
        Args:
            query_embedding (List[float]): The embedding vector to search with
            table_name (str): Database table to search within
            embedding_column (str): Column name containing embeddings
            limit (int): Maximum results to return
            similarity_threshold (float): Minimum similarity score (0-1)
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            list: List of similar documents with similarity scores
        """
        try:
            if not query_embedding or len(query_embedding) != self.config.embedding_dimensions:
                logging.error(f"Invalid query embedding dimension: {len(query_embedding) if query_embedding else 0}")
                return []
            
            # Convert embedding to PostgreSQL vector format
            vector_str = f"[{','.join(str(x) for x in query_embedding)}]"
            
            # Build pgvector similarity search query
            query = f"""
                SELECT 
                    book_id,
                    1 - (1 - ({embedding_column} <=> %s::vector)) as similarity_score,
                    * EXCEPT ({embedding_column})
                FROM {table_name}
                WHERE 1 - ({embedding_column} <=> %s::vector) >= %s
                ORDER BY similarity_score DESC
                LIMIT %s
            """
            
            result = self._execute_query(
                query=query,
                params=(vector_str, vector_str, similarity_threshold, limit),
                trace=trace,
                next_trace=next_trace
            )
            
            logging.info(f"Found {len(result)} similar books with threshold {similarity_threshold}")
            return result
            
        except Exception as e:
            logging.error(f"Error searching for similar books: {e}", exc_info=True)
            return []


    def calculate_cosine_similarity(
        self,
        vector1: List[float],
        vector2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embedding vectors.
        
        Args:
            vector1 (List[float]): First vector
            vector2 (List[float]): Second vector
        
        Returns:
            float: Cosine similarity score (0-1)
        """
        try:
            if not vector1 or not vector2 or len(vector1) != len(vector2):
                return 0.0
            
            v1 = np.array(vector1, dtype=np.float32)
            v2 = np.array(vector2, dtype=np.float32)
            
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(np.clip(similarity, 0.0, 1.0))
            
        except Exception as e:
            logging.error(f"Error calculating cosine similarity: {e}")
            return 0.0


    def fetch_similar_reasoning(
        self,
        book_id: str,
        table_name: str,
        embedding_column: str,
        limit: int = 5,
        trace=None,
        next_trace=None
    ) -> List[Dict[str, Any]]:
        """
        Fetch semantically similar reasoning paragraphs or excerpts for a specific book.
        Used for finding related content within the same book.
        
        Args:
            book_id (str): The book ID to find similar reasoning for
            table_name (str): Table containing the excerpts/sections
            embedding_column (str): Column containing embeddings
            limit (int): Maximum results to return
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            list: List of similar content with scores
        """
        try:
            # First, get the embedding for the reference book
            ref_query = f"""
                SELECT {embedding_column}
                FROM {table_name}
                WHERE book_id = %s
                LIMIT 1
            """
            
            ref_result = self._execute_query(
                query=ref_query,
                params=(book_id,),
                trace=trace,
                next_trace=next_trace
            )
            
            if not ref_result:
                logging.warning(f"No reference embedding found for book {book_id}")
                return []
            
            ref_embedding = ref_result[0].get(embedding_column)
            if not ref_embedding:
                return []
            
            # Search for similar embeddings within the same book
            query = f"""
                SELECT 
                    excerpt_id,
                    excerpt_text,
                    1 - ({embedding_column} <=> %s::vector) as similarity_score
                FROM {table_name}
                WHERE book_id = %s AND excerpt_id != %s
                ORDER BY similarity_score DESC
                LIMIT %s
            """
            
            result = self._execute_query(
                query=query,
                params=(ref_embedding, book_id, book_id, limit),
                trace=trace,
                next_trace=next_trace
            )
            
            logging.info(f"Found {len(result)} similar reasoning paragraphs for book {book_id}")
            return result
            
        except Exception as e:
            logging.error(f"Error fetching similar reasoning: {e}", exc_info=True)
            return []


    def normalize_embedding(
        self,
        embedding: List[float]
    ) -> List[float]:
        """
        Normalize an embedding vector to unit length.
        
        Args:
            embedding (List[float]): The embedding vector to normalize
        
        Returns:
            list: Normalized embedding vector
        """
        try:
            if not embedding:
                return []
            
            v = np.array(embedding, dtype=np.float32)
            norm = np.linalg.norm(v)
            
            if norm == 0:
                return embedding
            
            normalized = (v / norm).tolist()
            return normalized
            
        except Exception as e:
            logging.error(f"Error normalizing embedding: {e}")
            return embedding


    def batch_generate_embeddings(
        self,
        texts: List[str],
        trace=None,
        next_trace=None
    ) -> Dict[str, List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts (List[str]): List of texts to embed
            trace: Trace dictionary for logging
            next_trace: Next trace object for tool chaining
        
        Returns:
            dict: Dictionary mapping text to embedding vector
        """
        embeddings = {}
        
        try:
            for text in texts:
                if not text or not isinstance(text, str):
                    continue
                
                embedding = self.generate_embedding(
                    text=text.strip(),
                    trace=trace,
                    next_trace=next_trace
                )
                
                if embedding:
                    embeddings[text] = embedding
            
            logging.info(f"Generated {len(embeddings)} embeddings from {len(texts)} texts")
            return embeddings
            
        except Exception as e:
            logging.error(f"Error batch generating embeddings: {e}", exc_info=True)
            return embeddings

