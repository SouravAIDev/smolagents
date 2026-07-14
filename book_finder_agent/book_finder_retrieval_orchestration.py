import logging
import traceback
from typing import Dict, List, Optional, Any, Tuple
from collections import OrderedDict
import math

from book_finder_agent.book_finder_scoring_engine import ScoringEngine


class RetrievalOrchestration:
    """Orchestrates the multi-stage retrieval pipeline for the BookFinderAgent.
    
    Manages vector similarity searches across filter pathways, deduplication
    of results, chunk retrieval, and multi-dimensional scoring.
    """

    @staticmethod
    def calculate_ids_per_filter(
        max_book_ids: int,
        active_filter_count: int,
        strategy: str = "dynamic"
    ) -> int:
        """Calculate dynamic limit for IDs retrieved per filter.
        
        Uses formula: min(ceil(max_book_ids / active_filters), 15)
        This ensures even distribution across filters while respecting a hard limit.
        
        Args:
            max_book_ids: Total maximum book IDs across all filters.
            active_filter_count: Number of active filters in current query.
            strategy: 'dynamic' uses formula above, 'fixed' returns 15.
        
        Returns:
            Maximum IDs to retrieve per individual filter.
        """
        if active_filter_count <= 0:
            logging.warning(f"active_filter_count is {active_filter_count}, returning 15 (default)")
            return 15
        
        try:
            if strategy == "fixed":
                return 15
            
            # Dynamic strategy: distribute max_book_ids across filters evenly
            ids_per_filter = math.ceil(max_book_ids / active_filter_count)
            # Hard cap at 15 per filter
            ids_per_filter = min(ids_per_filter, 15)
            
            logging.debug(
                f"Dynamic ids_per_filter calculation: max_book_ids={max_book_ids}, "
                f"active_filters={active_filter_count}, result={ids_per_filter}"
            )
            return max(1, ids_per_filter)  # Ensure at least 1
        
        except Exception as e:
            logging.error(f"Error calculating ids_per_filter: {e}")
            return 15

    @staticmethod
    def _retrieve_ids(
        agent,
        filter_pathways: Dict[str, Any],
        max_book_ids: int,
        ids_per_filter_strategy: str = "dynamic",
        next_trace: Optional[Dict] = None,
        trace: Optional[Dict] = None
    ) -> Tuple[List[str], Dict[str, Dict], bool]:
        """Execute parallel vector similarity searches across active filters.
        
        Queries all active filter pathways to retrieve matching book ISBNs,
        applies dynamic per-filter limits, deduplicates results, and returns
        unified ISBN list with accompanying metadata.
        
        Args:
            agent: BookFinderAgent instance with sql_executor_tool and config.
            filter_pathways: Dict of active filters with their embeddings and configs.
                            Example: {"genre": {"embedding": [...], "config": {...}}, ...}
            max_book_ids: Total maximum book IDs to retrieve across all filters.
            ids_per_filter_strategy: Strategy for calculating per-filter limit.
            next_trace: Optional trace handle for downstream observability.
            trace: Optional trace dict for execution tracking.
        
        Returns:
            Tuple of (isbn_list, metadata_dict, should_reduce_rows_flag).
        """
        try:
            active_filter_count = len([k for k, v in filter_pathways.items() if v is not None])
            if active_filter_count == 0:
                logging.warning("No active filters provided")
                return [], {}, False
            
            ids_per_filter = RetrievalOrchestration.calculate_ids_per_filter(
                max_book_ids,
                active_filter_count,
                strategy=ids_per_filter_strategy
            )
            
            # Dictionary to store results, keyed by ISBN for deduplication
            unified_results = OrderedDict()
            filter_intersection_count = {}
            
            # Execute vector search for each active filter
            for filter_type, filter_data in filter_pathways.items():
                if filter_data is None:
                    continue
                
                try:
                    logging.debug(f"Executing vector search for filter: {filter_type}")
                    
                    # Build parameterized query for this filter's vector search
                    # This is a placeholder - actual query depends on agent's loaded templates
                    query = agent.queries.get("retrieve_book_vector_search", "")
                    if not query:
                        logging.warning(f"No query template for {filter_type}")
                        continue
                    
                    # Execute search
                    embedding = filter_data.get('embedding')
                    similarity_threshold = filter_data.get('similarity_threshold', agent.config.similarity_threshold)
                    
                    params = (embedding, similarity_threshold, ids_per_filter)
                    results = agent.sql_executor_tool.run(
                        sql_query=query,
                        params=params,
                        next_trace=next_trace,
                        trace=trace
                    ) or []
                    
                    logging.debug(f"Retrieved {len(results)} books for filter {filter_type}")
                    
                    # Deduplicate and accumulate results
                    for result in results:
                        isbn = result.get('isbn') or result.get('book_id')
                        if isbn:
                            if isbn not in unified_results:
                                unified_results[isbn] = result.copy()
                                filter_intersection_count[isbn] = 0
                            # Track filter intersections for document overlap scoring
                            filter_intersection_count[isbn] += 1
                
                except Exception as e:
                    logging.error(f"Error retrieving IDs for filter {filter_type}: {e}", exc_info=True)
                    continue
            
            if not unified_results:
                logging.warning(f"No results retrieved across {active_filter_count} filters")
                return [], {}, False
            
            # Determine if row reduction is needed
            should_reduce = len(unified_results) >= max_book_ids * 0.9
            
            # Add filter intersection data to each result
            metadata_dict = {}
            for isbn, result_data in unified_results.items():
                result_data['filter_intersections'] = {filter_type: 1 for filter_type in filter_pathways if filter_type in str(result_data)}
                result_data['filter_intersection_count'] = filter_intersection_count.get(isbn, 0)
                metadata_dict[isbn] = result_data
            
            isbn_list = list(unified_results.keys())
            logging.info(
                f"Retrieved {len(isbn_list)} unique books from {active_filter_count} filters, "
                f"should_reduce={should_reduce}"
            )
            
            return isbn_list, metadata_dict, should_reduce
        
        except Exception as e:
            logging.error(f"Error in _retrieve_ids: {e}", exc_info=True)
            return [], {}, False

    @staticmethod
    def _retrieve_content(
        agent,
        book_ids: List[str],
        query_embedding: List[float],
        next_trace: Optional[Dict] = None,
        trace: Optional[Dict] = None
    ) -> List[Dict]:
        """Retrieve supporting manuscript chunks for book candidates.
        
        Executes vector similarity search on the book content/chunks table,
        filters by similarity threshold, and retrieves up to max_chunks_to_use
        chunks sorted by cosine distance.
        
        Args:
            agent: BookFinderAgent instance with config and sql_executor_tool.
            book_ids: List of book ISBNs to retrieve chunks for.
            query_embedding: Query vector for semantic similarity search.
            next_trace: Optional trace handle.
            trace: Optional trace dict.
        
        Returns:
            List of chunk dictionaries with text, similarity scores, and metadata.
        """
        if not book_ids or not query_embedding:
            logging.warning("book_ids or query_embedding is empty")
            return []
        
        try:
            query_template = agent.queries.get("retrieve_book_chunks", "")
            if not query_template:
                logging.warning("No query template for retrieve_book_chunks")
                return []
            
            # Build parameterized query for chunk retrieval
            params = (
                query_embedding,
                agent.config.max_chunks_to_use,
                agent.config.similarity_threshold,
                tuple(book_ids)
            )
            
            chunks = agent.sql_executor_tool.run(
                sql_query=query_template,
                params=params,
                next_trace=next_trace,
                trace=trace
            ) or []
            
            logging.info(f"Retrieved {len(chunks)} chunks for {len(book_ids)} books")
            return chunks
        
        except Exception as e:
            logging.error(f"Error retrieving chunks: {e}", exc_info=True)
            return []

    @staticmethod
    def _post_process(
        chunks: List[Dict],
        metadata_dict: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """Merge retrieved chunks with metadata and normalize data.
        
        Integrates supporting chunk content with book metadata, normalizes
        datetime and UUID fields, and builds unified book candidate objects
        ready for scoring.
        
        Args:
            chunks: List of chunk dicts from content table.
            metadata_dict: Dict of ISBN -> metadata from filter results.
        
        Returns:
            Updated metadata_dict with integrated chunk data.
        """
        if not chunks:
            logging.debug("No chunks to post-process")
            return metadata_dict
        
        try:
            # Group chunks by ISBN
            chunks_by_isbn = {}
            for chunk in chunks:
                isbn = chunk.get('isbn') or chunk.get('book_id')
                if isbn:
                    if isbn not in chunks_by_isbn:
                        chunks_by_isbn[isbn] = []
                    chunks_by_isbn[isbn].append(chunk)
            
            # Integrate chunks into metadata
            for isbn, book_data in metadata_dict.items():
                if isbn in chunks_by_isbn:
                    # Add chunks as supporting_chunks field
                    book_data['supporting_chunks'] = chunks_by_isbn[isbn]
                    
                    # Calculate average distance across chunks for semantic scoring
                    distances = [
                        float(c.get('cosine_distance', 1.0))
                        for c in chunks_by_isbn[isbn]
                        if c.get('cosine_distance') is not None
                    ]
                    if distances:
                        book_data['average_distance'] = sum(distances) / len(distances)
                else:
                    book_data['supporting_chunks'] = []
                    book_data['average_distance'] = 1.0  # No chunks found
            
            logging.debug(f"Post-processed {len(metadata_dict)} books with chunk integration")
            return metadata_dict
        
        except Exception as e:
            logging.error(f"Error in post-processing: {e}", exc_info=True)
            return metadata_dict

    @staticmethod
    def _calculate_scores(
        metadata_dict: Dict[str, Dict],
        user_query: str,
        active_filter_count: int,
        weight_sim: float = 0.45,
        weight_doc: float = 0.25,
        weight_key: float = 0.30
    ) -> Dict[str, Dict]:
        """Calculate multi-dimensional relevance scores for all book candidates.
        
        Orchestrates ScoringEngine to compute semantic similarity, document overlap,
        and keyword frequency scores, then combines them using weighted formula.
        
        Args:
            metadata_dict: Dict of ISBN -> book data to score.
            user_query: Original user query for keyword matching.
            active_filter_count: Count of active filters for document score normalization.
            weight_sim: Semantic similarity weight (default 0.45).
            weight_doc: Document overlap weight (default 0.25).
            weight_key: Keyword frequency weight (default 0.30).
        
        Returns:
            Updated metadata_dict with final_score and score_components added.
        """
        try:
            if not metadata_dict:
                logging.debug("metadata_dict is empty, no scoring needed")
                return metadata_dict
            
            # Validate weights
            total_weight = weight_sim + weight_doc + weight_key
            if abs(total_weight - 1.0) > 0.01:
                logging.warning(
                    f"Weights do not sum to 1.0: {weight_sim} + {weight_doc} + {weight_key} = {total_weight}"
                )
            
            # Score each book candidate
            for isbn, book_data in metadata_dict.items():
                book_data = ScoringEngine.aggregate_book_scores(
                    book_data,
                    active_filter_count,
                    user_query,
                    weight_sim=weight_sim,
                    weight_doc=weight_doc,
                    weight_key=weight_key
                )
                metadata_dict[isbn] = book_data
            
            # Sort by final_score descending
            sorted_books = sorted(
                metadata_dict.items(),
                key=lambda x: x[1].get('final_score', 0.0),
                reverse=True
            )
            
            # Return as ordered dict
            scored_dict = OrderedDict(sorted_books)
            logging.info(f"Scored {len(scored_dict)} books, top score={scored_dict[list(scored_dict.keys())[0]].get('final_score', 0.0):.4f}" if scored_dict else "No books to score")
            
            return scored_dict
        
        except Exception as e:
            logging.error(f"Error calculating scores: {e}", exc_info=True)
            return metadata_dict

    @staticmethod
    def prepare_retrieval_context(
        agent,
        user_query: str,
        filter_pathways: Dict[str, Any],
        next_trace: Optional[Dict] = None,
        trace: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Orchestrate the complete retrieval pipeline.
        
        Coordinates _retrieve_ids -> _retrieve_content -> _post_process -> _calculate_scores
        to produce a fully scored and ranked set of book candidates ready for LLM processing.
        
        Args:
            agent: BookFinderAgent instance with tools, config, and queries.
            user_query: Original user query string.
            filter_pathways: Dict of active filters with embeddings and configs.
            next_trace: Optional trace handle.
            trace: Optional trace dict.
        
        Returns:
            Dict containing:
            - scored_books: OrderedDict of ISBN -> scored book data, sorted by relevance
            - total_candidates: Total number of candidates before filtering
            - metadata_dict: Full metadata dict for all candidates
            - retrieval_stats: Stats about retrieval process
        """
        try:
            logging.info(f"Starting retrieval pipeline for query: {user_query}")
            
            # Stage 1: Retrieve ISBN lists from all filter pathways
            isbn_list, metadata_dict, should_reduce = RetrievalOrchestration._retrieve_ids(
                agent,
                filter_pathways,
                agent.config.max_book_ids,
                agent.config.ids_per_filter_strategy,
                next_trace,
                trace
            )
            
            if not isbn_list:
                logging.warning("No books retrieved in Stage 1")
                return {
                    'scored_books': OrderedDict(),
                    'total_candidates': 0,
                    'metadata_dict': {},
                    'retrieval_stats': {'stage_1_results': 0}
                }
            
            # Stage 2: Retrieve supporting chunks
            chunks = RetrievalOrchestration._retrieve_content(
                agent,
                isbn_list,
                filter_pathways.get('query_embedding'),
                next_trace,
                trace
            )
            
            # Stage 3: Post-process and merge chunks with metadata
            metadata_dict = RetrievalOrchestration._post_process(chunks, metadata_dict)
            
            # Stage 4: Calculate multi-dimensional scores
            active_filter_count = len([k for k, v in filter_pathways.items() if v is not None and k != 'query_embedding'])
            scored_books = RetrievalOrchestration._calculate_scores(
                metadata_dict,
                user_query,
                active_filter_count,
                weight_sim=agent.config.context_weight_score,
                weight_doc=agent.config.document_weight_score,
                weight_key=agent.config.keyword_weight_score
            )
            
            retrieval_stats = {
                'stage_1_results': len(isbn_list),
                'chunks_retrieved': len(chunks),
                'books_scored': len(scored_books),
                'should_reduce_rows': should_reduce,
                'active_filters': active_filter_count
            }
            
            logging.info(f"Retrieval pipeline complete: {retrieval_stats}")
            
            return {
                'scored_books': scored_books,
                'total_candidates': len(isbn_list),
                'metadata_dict': metadata_dict,
                'retrieval_stats': retrieval_stats
            }
        
        except Exception as e:
            logging.error(f"Error in retrieval pipeline: {e}", exc_info=True)
            return {
                'scored_books': OrderedDict(),
                'total_candidates': 0,
                'metadata_dict': {},
                'retrieval_stats': {'error': str(e)}
            }

