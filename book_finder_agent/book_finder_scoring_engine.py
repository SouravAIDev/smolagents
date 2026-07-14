import logging
import math
from typing import Dict, List, Optional, Tuple
from collections import Counter
import re


class ScoringEngine:
    """Multi-dimensional scoring engine for book relevance ranking.
    
    Implements the hybrid scoring formula:
    Final Score = (weight_sim * S_sim) + (weight_doc * S_doc) + (weight_key * S_key)
    
    Where:
    - S_sim: Semantic similarity score [0, 1] from vector distance
    - S_doc: Document overlap score [0, 1] from filter intersections
    - S_key: Keyword/n-gram frequency score [0, 1] from text matching
    """

    # N-gram sizes to consider for keyword matching
    NGRAM_SIZES = [1, 2, 3]
    
    # Minimum term frequency to consider (filters noise)
    MIN_TERM_FREQUENCY = 0

    @staticmethod
    def calculate_semantic_similarity_score(
        average_distance: Optional[float],
        normalize: bool = True
    ) -> float:
        """Convert cosine distance to similarity score in [0, 1] range.
        
        Args:
            average_distance: Average cosine distance from vector search (typically 0.0-2.0).
                            Lower values indicate higher similarity.
            normalize: If True, apply 1 - distance conversion. Default True.
            
        Returns:
            Similarity score in [0, 1] range.
        """
        if average_distance is None:
            logging.warning("average_distance is None, returning 0.0")
            return 0.0
        
        try:
            distance = float(average_distance)
            # Convert distance to similarity: similarity = 1 - distance (for cosine distance)
            similarity = max(0.0, 1.0 - distance) if normalize else distance
            return min(1.0, max(0.0, similarity))  # Clamp to [0, 1]
        except (ValueError, TypeError) as e:
            logging.error(f"Error calculating semantic similarity for distance={average_distance}: {e}")
            return 0.0

    @staticmethod
    def calculate_document_overlap_score(
        filter_intersections: Dict[str, int],
        active_filter_count: int
    ) -> float:
        """Calculate normalized score based on filter intersection density.
        
        Counts how many filters matched this book candidate across filter pathways.
        Higher intersection count indicates the book matches more user criteria.
        
        Args:
            filter_intersections: Dict mapping filter types to occurrence counts.
                                 Example: {"genre": 2, "author": 1}
            active_filter_count: Total number of active filters in the query.
                                Used for normalization.
        
        Returns:
            Normalized overlap score in [0, 1] range.
        """
        if active_filter_count <= 0:
            logging.warning(f"active_filter_count is {active_filter_count}, returning 0.0")
            return 0.0
        
        if not filter_intersections:
            logging.debug("filter_intersections is empty, returning 0.0")
            return 0.0
        
        try:
            # Count total intersections (sum of all filter matches)
            total_intersections = sum(filter_intersections.values())
            # Normalize by active filter count: max possible intersections
            overlap_score = min(1.0, total_intersections / active_filter_count)
            return max(0.0, overlap_score)
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logging.error(f"Error calculating document overlap score: {e}")
            return 0.0

    @staticmethod
    def _tokenize_query(query: str) -> List[str]:
        """Tokenize query into overlapping n-grams.
        
        Args:
            query: User query string.
        
        Returns:
            List of normalized n-grams of sizes 1-3.
        """
        if not query or not isinstance(query, str):
            return []
        
        # Normalize: lowercase, remove special chars, split on whitespace
        normalized = re.sub(r'[^a-z0-9\s]', '', query.lower())
        tokens = normalized.split()
        
        ngrams = []
        for size in ScoringEngine.NGRAM_SIZES:
            for i in range(len(tokens) - size + 1):
                ngrams.append(' '.join(tokens[i:i+size]))
        
        return ngrams

    @staticmethod
    def _extract_text_from_book(book_data: Dict) -> str:
        """Extract searchable text content from book data structure.
        
        Concatenates title, summary, content chunks, genre, author, and other
        textual attributes into a unified corpus for n-gram matching.
        
        Args:
            book_data: Book metadata and content dictionary.
        
        Returns:
            Concatenated text content for the book.
        """
        text_parts = []
        
        # Extract from standard book fields
        if book_data.get('title'):
            text_parts.append(str(book_data['title']))
        if book_data.get('summary'):
            text_parts.append(str(book_data['summary']))
        if book_data.get('genre'):
            text_parts.append(str(book_data['genre']))
        if book_data.get('author'):
            text_parts.append(str(book_data['author']))
        if book_data.get('publisher'):
            text_parts.append(str(book_data['publisher']))
        
        # Extract from supporting chunks if present
        chunks = book_data.get('supporting_chunks', [])
        if isinstance(chunks, list):
            for chunk in chunks:
                if isinstance(chunk, dict) and chunk.get('chunk_text'):
                    text_parts.append(str(chunk['chunk_text']))
                elif isinstance(chunk, str):
                    text_parts.append(chunk)
        
        # Join all text with spaces for unified corpus
        return ' '.join(text_parts).lower()

    @staticmethod
    def calculate_keyword_score(
        query: str,
        book_data: Dict,
        min_term_frequency: int = 0
    ) -> float:
        """Calculate TF-IDF-based n-gram frequency score.
        
        Tokenizes user query into overlapping n-grams (1-3 word combinations),
        counts occurrences in book text, and normalizes using term frequency.
        
        Args:
            query: User query string.
            book_data: Book metadata and content dictionary.
            min_term_frequency: Minimum frequency threshold (default 0).
        
        Returns:
            Keyword score in [0, 1] range.
        """
        if not query or not book_data:
            logging.debug("query or book_data is empty, returning 0.0")
            return 0.0
        
        try:
            # Tokenize query into n-grams
            query_ngrams = ScoringEngine._tokenize_query(query)
            if not query_ngrams:
                logging.debug("No n-grams extracted from query, returning 0.0")
                return 0.0
            
            # Extract unified text from book
            book_text = ScoringEngine._extract_text_from_book(book_data)
            if not book_text:
                logging.debug("No text extracted from book_data, returning 0.0")
                return 0.0
            
            # Normalize book text
            book_text_normalized = re.sub(r'[^a-z0-9\s]', '', book_text.lower())
            
            # Count n-gram frequencies in book text
            ngram_counts = Counter()
            for ngram in query_ngrams:
                # Count non-overlapping occurrences for this n-gram
                count = len(re.findall(r'\b' + re.escape(ngram) + r'\b', book_text_normalized))
                if count >= min_term_frequency:
                    ngram_counts[ngram] = count
            
            if not ngram_counts:
                logging.debug(f"No matching n-grams found in book text")
                return 0.0
            
            # Calculate TF-IDF-like score: sum of log-transformed frequencies
            # Use log(1 + freq) to dampen the effect of very frequent terms
            total_score = sum(math.log(1.0 + freq) for freq in ngram_counts.values())
            
            # Normalize by maximum possible score (all query n-grams with freq=len(book_tokens))
            # Use a conservative estimate to avoid division by very small numbers
            book_token_count = len(book_text_normalized.split())
            max_possible_score = len(query_ngrams) * math.log(1.0 + max(10, book_token_count // 100))
            
            if max_possible_score <= 0:
                keyword_score = 0.0
            else:
                keyword_score = min(1.0, total_score / max_possible_score)
            
            logging.debug(
                f"Keyword score calculation: query_ngrams={len(query_ngrams)}, "
                f"matched_ngrams={len(ngram_counts)}, score={keyword_score:.4f}"
            )
            return max(0.0, keyword_score)
        
        except Exception as e:
            logging.error(f"Error calculating keyword score: {e}", exc_info=True)
            return 0.0

    @staticmethod
    def combine_scores(
        semantic_score: float,
        document_score: float,
        keyword_score: float,
        weight_sim: float = 0.45,
        weight_doc: float = 0.25,
        weight_key: float = 0.30
    ) -> Tuple[float, Dict]:
        """Combine three component scores using weighted formula.
        
        Formula: Final = (weight_sim * S_sim) + (weight_doc * S_doc) + (weight_key * S_key)
        
        Args:
            semantic_score: Semantic similarity component [0, 1].
            document_score: Document overlap component [0, 1].
            keyword_score: Keyword frequency component [0, 1].
            weight_sim: Weight for semantic component (default 0.45).
            weight_doc: Weight for document component (default 0.25).
            weight_key: Weight for keyword component (default 0.30).
        
        Returns:
            Tuple of (final_score [0, 1], component_dict with breakdown).
        """
        # Validate weights
        total_weight = weight_sim + weight_doc + weight_key
        if abs(total_weight - 1.0) > 0.01:  # Allow small floating point error
            logging.warning(
                f"Weights do not sum to 1.0: {weight_sim} + {weight_doc} + {weight_key} = {total_weight}"
            )
        
        try:
            # Clamp component scores to [0, 1]
            s_sim = max(0.0, min(1.0, semantic_score or 0.0))
            s_doc = max(0.0, min(1.0, document_score or 0.0))
            s_key = max(0.0, min(1.0, keyword_score or 0.0))
            
            # Calculate weighted sum
            final_score = (weight_sim * s_sim) + (weight_doc * s_doc) + (weight_key * s_key)
            final_score = max(0.0, min(1.0, final_score))
            
            components = {
                'S_sim': s_sim,
                'S_doc': s_doc,
                'S_key': s_key,
                'weight_sim': weight_sim,
                'weight_doc': weight_doc,
                'weight_key': weight_key,
                'final_score': final_score
            }
            
            return final_score, components
        
        except Exception as e:
            logging.error(f"Error combining scores: {e}", exc_info=True)
            return 0.0, {}

    @staticmethod
    def aggregate_book_scores(
        book: Dict,
        active_filter_count: int,
        user_query: str,
        weight_sim: float = 0.45,
        weight_doc: float = 0.25,
        weight_key: float = 0.30,
        min_keyword_freq: int = 0
    ) -> Dict:
        """Orchestrate all scoring components for a single book candidate.
        
        Args:
            book: Book candidate dict containing metadata, chunks, and filter data.
            active_filter_count: Count of active filters in current query.
            user_query: Original user query string.
            weight_sim: Weight for semantic component (default 0.45).
            weight_doc: Weight for document component (default 0.25).
            weight_key: Weight for keyword component (default 0.30).
            min_keyword_freq: Minimum n-gram frequency threshold.
        
        Returns:
            Book dict updated with 'final_score' and 'score_components' fields.
        """
        if not book:
            return {}
        
        try:
            # Component 1: Semantic similarity from vector search
            avg_distance = book.get('average_distance', None)
            semantic_score = ScoringEngine.calculate_semantic_similarity_score(avg_distance)
            
            # Component 2: Document overlap from filter intersections
            filter_intersections = book.get('filter_intersections', {})
            document_score = ScoringEngine.calculate_document_overlap_score(
                filter_intersections,
                active_filter_count
            )
            
            # Component 3: Keyword frequency from n-gram matching
            keyword_score = ScoringEngine.calculate_keyword_score(
                user_query,
                book,
                min_term_frequency=min_keyword_freq
            )
            
            # Combine scores
            final_score, components = ScoringEngine.combine_scores(
                semantic_score,
                document_score,
                keyword_score,
                weight_sim=weight_sim,
                weight_doc=weight_doc,
                weight_key=weight_key
            )
            
            # Update book with scores
            book['final_score'] = final_score
            book['score_components'] = components
            
            logging.debug(
                f"Scored book (ISBN={book.get('isbn', 'unknown')}): "
                f"final_score={final_score:.4f}, S_sim={semantic_score:.4f}, "
                f"S_doc={document_score:.4f}, S_key={keyword_score:.4f}"
            )
            
            return book
        
        except Exception as e:
            logging.error(f"Error aggregating scores for book: {e}", exc_info=True)
            book['final_score'] = 0.0
            book['score_components'] = {}
            return book

