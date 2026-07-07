import pytest
import json
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from book_finder_agent import BookFinderAgent_v2
from book_helper import BookFilterType, FilterTypeSchema, BOOK_FILTER_MAPPING
from book_finder_agent_setup import BookFinderAgentSetup
from book_finder_agent_trace import BookFinderAgentTrace


class TestBookFinderAgent:
    """
    Comprehensive test suite for BookFinderAgent_v2.
    Tests all three execution flows (A, B, C) and core functionality.
    """
    
    @pytest.fixture
    def agent(self):
        """
        Fixture providing a BookFinderAgent_v2 instance with mocked tools.
        """
        agent = BookFinderAgent_v2()
        
        # Mock configuration
        agent.config = BookFinderAgentSetup()
        agent.data = {}
        agent.agent_id = "test-agent-123"
        
        # Mock tools
        agent.sql_executor_tool = Mock()
        agent.llm_configuration_tool = Mock()
        agent.semantic_similarity_tool = Mock()
        agent.citation_tool = Mock()
        
        # Mock utilities
        agent.queries = {
            'vector_query': 'SELECT * FROM table WHERE embedding <=> %s',
            'fetch_show_more_docs': 'SELECT * FROM context WHERE session_id = %s'
        }
        
        return agent
    
    def test_agent_initialization(self, agent):
        """
        Test that agent initializes with correct configuration.
        """
        assert agent.config is not None
        assert agent.config.max_books_per_response == 3
        assert agent.config.similarity_threshold == 0.3
        assert agent.config.filter_similarity_threshold == 0.65
    
    def test_filter_type_schema_validation(self):
        """
        Test FilterTypeSchema validates and normalizes inputs.
        """
        # Valid input
        schema = FilterTypeSchema(
            book_title="Python programming",
            genre_details="Technology",
            author_details="Guido van Rossum"
        )
        
        params = schema.get_run_params()
        assert len(params) == 3
        assert params['book_title'] == "Python programming"
        assert params['genre_details'] == "Technology"
    
    def test_filter_type_schema_with_none_values(self):
        """
        Test that None values are excluded from run_params.
        """
        schema = FilterTypeSchema(
            book_title="Learning Python",
            genre_details=None,
            author_details=None
        )
        
        params = schema.get_run_params()
        assert len(params) == 1
        assert 'book_title' in params
        assert 'genre_details' not in params
    
    def test_book_filter_mapping_completeness(self):
        """
        Test that BOOK_FILTER_MAPPING contains all expected filter types.
        """
        expected_filters = {
            BookFilterType.AUTHOR_DETAILS,
            BookFilterType.BOOK_TITLE,
            BookFilterType.BOOK_SUMMARY,
            BookFilterType.GENRE_DETAILS,
            BookFilterType.PUBLISHER_DETAILS,
            BookFilterType.SUPPORTING_EXCERPTS
        }
        
        for filter_type in expected_filters:
            assert filter_type in BOOK_FILTER_MAPPING
            assert BOOK_FILTER_MAPPING[filter_type].table is not None
            assert BOOK_FILTER_MAPPING[filter_type].search_column is not None
    
    @patch('book_finder_agent.BookFinderAgent_v2._execute_semantic_search')
    def test_flow_a_execution(self, mock_search, agent):
        """
        Test Flow A (standard search) execution path.
        """
        # Mock embedding generation
        agent.generate_embedding = Mock(return_value=[0.1] * 1536)
        
        # Mock semantic search results
        mock_search.return_value = [
            {
                'book_id': str(uuid.uuid4()),
                'title': 'Test Book 1',
                'author_name': 'Author 1',
                'similarity_score': 0.85
            }
        ]
        
        # Mock excerpt retrieval
        agent._retrieve_excerpts = Mock(return_value=[])
        
        # Mock session insertion
        agent.insert_retrieved_documents = Mock()
        
        # Mock LLM response
        agent.llm_configuration_tool.run = Mock(
            return_value={'response': 'Found relevant books...'}
        )
        
        # Mock citation extraction
        agent.extract_citations_from_response = Mock(return_value=[])
        
        # Execute
        response, docs, citations, bypass = agent._execute_flow_a(
            session_id=str(uuid.uuid4()),
            user_query="Find science fiction books"
        )
        
        assert response is not None
        assert isinstance(docs, list)
        assert isinstance(citations, list)
        assert isinstance(bypass, bool)
    
    def test_flow_b_pagination(self, agent):
        """
        Test Flow B (pagination) execution path.
        """
        session_id = str(uuid.uuid4())
        
        # Mock undisplayed books retrieval
        agent.fetch_undisplayed_books = Mock(return_value=[
            {
                'book_id': str(uuid.uuid4()),
                'title': 'Test Book 2',
                'similarity_score': 0.75
            }
        ])
        
        # Mock display state update
        agent.mark_books_as_displayed = Mock()
        
        # Execute
        response, docs, citations, bypass = agent._execute_flow_b(
            session_id=session_id
        )
        
        assert response is not None
        assert len(docs) > 0
        agent.fetch_undisplayed_books.assert_called_once()
        agent.mark_books_as_displayed.assert_called_once()
    
    def test_flow_c_prefiltered_query(self, agent):
        """
        Test Flow C (pre-filtered) execution path.
        """
        session_id = str(uuid.uuid4())
        filters = {'genre': 'Science Fiction'}
        
        # Mock filtered documents retrieval
        agent.fetch_filtered_documents = Mock(return_value=[
            {
                'book_id': str(uuid.uuid4()),
                'title': 'Test Book 3',
                'genre': 'Science Fiction'
            }
        ])
        
        # Execute
        response, docs, citations, bypass = agent._execute_flow_c(
            session_id=session_id,
            active_filters=filters
        )
        
        assert response is not None
        assert len(docs) > 0
        agent.fetch_filtered_documents.assert_called_once()
    
    def test_embedding_generation(self, agent):
        """
        Test embedding generation with dimension validation.
        """
        agent.semantic_similarity_tool.run = Mock(
            return_value={'embedding': [0.1] * 1536}
        )
        
        embedding = agent.generate_embedding("Test query")
        
        assert embedding is not None
        assert len(embedding) == agent.config.embedding_dimensions
    
    def test_score_calculation(self, agent):
        """
        Test final score calculation with weighted components.
        """
        books = {
            str(uuid.uuid4()): {
                'title': 'Book 1',
                'context_score': 0.8,
                'document_score': 0.9,
                'keyword_score': 0.7,
                'supporting_excerpts': ['excerpt1']
            }
        }
        
        agent.calculate_final_scores(
            books=books,
            context_weight=0.5,
            document_weight=0.2,
            keyword_weight=0.3,
            chunk_boost=0.2
        )
        
        for book_id, book_data in books.items():
            assert 'final_score' in book_data
            assert 0 <= book_data['final_score'] <= 1
    
    def test_citation_extraction(self, agent):
        """
        Test citation extraction from LLM response.
        """
        response_text = "According to [source_0], the book teaches [source_1] concepts."
        retrieved_docs = [
            {
                'book_id': str(uuid.uuid4()),
                'title': 'Book A',
                'author': 'Author A',
                'isbn': '123-456-789'
            },
            {
                'book_id': str(uuid.uuid4()),
                'title': 'Book B',
                'author': 'Author B',
                'isbn': '987-654-321'
            }
        ]
        
        citations = agent.extract_citations_from_response(
            response_text=response_text,
            retrieved_docs=retrieved_docs
        )
        
        assert len(citations) <= len(retrieved_docs)
        for citation in citations:
            assert 'title' in citation or 'book_id' in citation
    
    def test_book_row_reduction(self, agent):
        """
        Test reducing book rows based on score threshold.
        """
        books = {
            str(uuid.uuid4()): {'title': 'High Score', 'final_score': 0.95},
            str(uuid.uuid4()): {'title': 'Medium Score', 'final_score': 0.55},
            str(uuid.uuid4()): {'title': 'Low Score', 'final_score': 0.15},
            str(uuid.uuid4()): {'title': 'Below Threshold', 'final_score': 0.05}
        }
        
        reduced = agent.reduce_book_rows(
            filtered_books=books,
            threshold=0.3,
            min_rows=2
        )
        
        # Should keep at least 2 rows
        assert len(reduced) >= 2
        # Should not include score below threshold if min_rows met
        scores = [book['final_score'] for book in reduced.values()]
        assert all(score >= 0.3 or len(scores) < 3 for score in scores)
    
    def test_datetime_formatting(self, agent):
        """
        Test datetime formatting for LLM consumption.
        """
        data = [
            {
                'title': 'Book 1',
                'publication_date': datetime(2023, 5, 15),
                'metadata': {
                    'created_at': datetime(2023, 1, 10)
                }
            }
        ]
        
        formatted = agent._format_datetimes_for_llm(data)
        
        # Check date was converted to uppercase MMM-DD-YYYY format
        assert isinstance(formatted[0]['publication_date'], str)
        assert 'May' in formatted[0]['publication_date'] or 'MAY' in formatted[0]['publication_date']
    
    def test_isbn_extraction(self, agent):
        """
        Test ISBN extraction with fallback logic.
        """
        # Test with isbn field
        book1 = {'isbn': '123-456-789-0'}
        assert agent.extract_isbn_from_metadata(book1) == '123-456-789-0'
        
        # Test with isbn_13 fallback
        book2 = {'isbn_13': '978-0-123456-78-9', 'isbn_10': '0-123456-78-9'}
        assert agent.extract_isbn_from_metadata(book2) == '978-0-123456-78-9'
        
        # Test with no ISBN
        book3 = {'title': 'No ISBN'}
        assert agent.extract_isbn_from_metadata(book3) is None
    
    def test_genre_normalization(self, agent):
        """
        Test genre string normalization.
        """
        assert agent.normalize_genre("  Science  Fiction  ") == "science fiction"
        assert agent.normalize_genre("MYSTERY") == "mystery"
        assert agent.normalize_genre("Romance & Drama") == "romance & drama"
    
    def test_config_validation(self):
        """
        Test configuration validation.
        """
        config = BookFinderAgentSetup()
        
        assert config.max_books_per_response > 0
        assert config.similarity_threshold >= 0
        assert config.filter_similarity_threshold >= 0
        assert config.context_weight_score >= 0
        assert config.document_weight_score >= 0
        assert config.keyword_weight_score >= 0
    
    def test_trace_schema(self):
        """
        Test BookFinderAgentTrace schema.
        """
        trace = BookFinderAgentTrace(
            response="Test response",
            user_query="Test query",
            filters={'genre': 'Fiction'},
            target="Find fiction books",
            is_intersection=False,
            citations=[],
            error="",
            score_map={}
        )
        
        assert trace.response == "Test response"
        assert trace.user_query == "Test query"
        assert trace.filters == {'genre': 'Fiction'}


class TestAPIEndpoints:
    """
    Test suite for Flask API endpoints.
    """
    
    @pytest.fixture
    def client(self):
        """
        Fixture providing a test client for the Flask app.
        """
        from run import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_health_check_endpoint(self, client):
        """
        Test health check endpoint.
        """
        response = client.get('/utility/book-finder-agent/')
        assert response.status_code == 200
        assert "running" in response.data.decode().lower() or "agent" in response.data.decode().lower()
    
    def test_get_config_endpoint(self, client):
        """
        Test configuration retrieval endpoint.
        """
        response = client.get('/utility/book-finder-agent/get_config')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
    
    def test_prediction_endpoint_missing_payload(self, client):
        """
        Test prediction endpoint with invalid JSON.
        """
        response = client.post(
            '/utility/book-finder-agent/prediction',
            data="invalid json",
            content_type='application/json'
        )
        assert response.status_code == 400
    
    @patch('book_finder_agent.BookFinderAgent_v2.run')
    def test_prediction_endpoint_success(self, mock_run, client):
        """
        Test successful prediction endpoint call.
        """
        mock_run.return_value = (
            "Found relevant books",
            [{'book_id': 'test', 'title': 'Test Book'}],
            [],
            False
        )
        
        response = client.post(
            '/utility/book-finder-agent/prediction',
            json={
                'agent_id': 'test-agent',
                'concierge_id': 'test-concierge',
                'agent_arguments': {'user_query': 'Find books'}
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'response' in data
        assert 'agent_guide' in data or 'error' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

