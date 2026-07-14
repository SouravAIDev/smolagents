"""
Integration tests for the Book Finder Agent.

These tests validate the complete orchestration flow from HTTP request
through agent setup, execution, and response assembly.
"""
import json
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from book_finder_agent.run import app, fetch_book_data
from book_finder_agent.book_finder_helpers import BookFinderRequestSchema


class TestFlaskIntegration(unittest.TestCase):
    """Test Flask endpoint integration and request handling."""

    def setUp(self):
        """Set up test client and fixtures."""
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_home_endpoint(self):
        """Test the root endpoint returns status message."""
        response = self.client.get("/utility/book-content-rag-agent/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Book Finder Agent is running", response.data)

    def test_health_check_endpoint(self):
        """Test the health check endpoint."""
        response = self.client.get("/utility/book-content-rag-agent/health/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"healthy", response.data)

    def test_prediction_endpoint_missing_json(self):
        """Test prediction endpoint with missing JSON body."""
        response = self.client.post(
            "/utility/book-content-rag-agent/prediction",
            data=None,
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_prediction_endpoint_invalid_request(self):
        """Test prediction endpoint with invalid request schema."""
        response = self.client.post(
            "/utility/book-content-rag-agent/prediction",
            data=json.dumps({"invalid": "payload"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn("error", response_data)
        self.assertIn("details", response_data)

    def test_get_config_endpoint(self):
        """Test the configuration introspection endpoint."""
        response = self.client.get("/utility/book-content-rag-agent/get_config")
        self.assertIn(response.status_code, [200, 204])
        # Response may be empty (204) if config schema not available yet

    def test_get_llm_config_endpoint(self):
        """Test the LLM configuration introspection endpoint."""
        response = self.client.get("/utility/book-content-rag-agent/get_llm_config")
        self.assertIn(response.status_code, [200, 204])


class TestRequestValidation(unittest.TestCase):
    """Test request validation and normalization."""

    def test_valid_request_schema(self):
        """Test a valid BookFinderRequestSchema."""
        request_data = {
            "user_query": "Tell me about fiction books",
            "session_id": "test-session-123"
        }
        schema = BookFinderRequestSchema(**request_data)
        self.assertEqual(schema.user_query, "Tell me about fiction books")
        self.assertEqual(schema.session_id, "test-session-123")
        self.assertIsNone(schema.show_more_details)

    def test_request_schema_with_filters(self):
        """Test request schema with optional filters."""
        request_data = {
            "user_query": "Science fiction books",
            "session_id": "session-456",
            "filters": {
                "genre_details": "Science Fiction",
                "audience_details": "Adults"
            }
        }
        schema = BookFinderRequestSchema(**request_data)
        filters_dict = schema.get_filters_dict()
        self.assertIn("genre_details", filters_dict)
        self.assertEqual(filters_dict["genre_details"], "Science Fiction")

    def test_pagination_request_detection(self):
        """Test detection of pagination requests."""
        pagination_request = {
            "user_query": "More books",
            "session_id": "session-789",
            "show_more_details": {"length": 5}
        }
        schema = BookFinderRequestSchema(**pagination_request)
        self.assertTrue(schema.is_pagination_request())

    def test_missing_required_field_user_query(self):
        """Test validation error for missing user_query."""
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            BookFinderRequestSchema(
                session_id="session-123",
                user_query=""  # Empty string should fail min_length=1
            )

    def test_missing_required_field_session_id(self):
        """Test validation error for missing session_id."""
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            BookFinderRequestSchema(
                user_query="Valid query"
                # Missing session_id
            )


class TestFetchBookDataOrchestration(unittest.TestCase):
    """Test the fetch_book_data orchestration logic."""

    def test_fetch_book_data_with_valid_request(self):
        """Test fetch_book_data with a valid request."""
        request_data = {
            "user_query": "Fiction books",
            "session_id": "test-session"
        }
        schema = BookFinderRequestSchema(**request_data)
        trace = {}
        
        # Mock the agent to avoid actual database calls
        with patch("book_finder_agent.run.BookFinderAgent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            mock_agent.run.return_value = {
                "response_text": "Test response",
                "retrieved_books": [],
                "citations": [],
                "bypass_orchestrator_response": False
            }
            
            response_text, books, citations, bypass_flag = fetch_book_data(schema, trace)
            
            self.assertEqual(response_text, "Test response")
            self.assertEqual(books, [])
            self.assertEqual(citations, [])
            self.assertFalse(bypass_flag)

    def test_fetch_book_data_error_handling(self):
        """Test fetch_book_data error handling and fallback."""
        request_data = {
            "user_query": "Test query",
            "session_id": "test-session"
        }
        schema = BookFinderRequestSchema(**request_data)
        trace = {}
        
        # Mock the agent to raise an exception
        with patch("book_finder_agent.run.BookFinderAgent") as mock_agent_class:
            mock_agent_class.side_effect = Exception("Database connection failed")
            
            response_text, books, citations, bypass_flag = fetch_book_data(schema, trace)
            
            # Should return fallback response
            self.assertIn("error", response_text.lower())
            self.assertEqual(books, [])
            self.assertEqual(citations, [])
            self.assertFalse(bypass_flag)

    def test_fetch_book_data_response_tuple_format(self):
        """Test that fetch_book_data always returns a 4-tuple."""
        request_data = {
            "user_query": "Test query",
            "session_id": "test-session"
        }
        schema = BookFinderRequestSchema(**request_data)
        trace = {}
        
        with patch("book_finder_agent.run.BookFinderAgent"):
            result = fetch_book_data(schema, trace)
            
            # Verify 4-tuple structure
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 4)
            self.assertIsInstance(result[0], str)  # response_text
            self.assertIsInstance(result[1], list)  # retrieved_books
            self.assertIsInstance(result[2], list)  # citations
            self.assertIsInstance(result[3], bool)  # bypass_orchestrator_response


class TestResponseContract(unittest.TestCase):
    """Test the response contract compliance."""

    def setUp(self):
        """Set up test client."""
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_prediction_response_structure(self):
        """Test that prediction endpoint returns compliant response structure."""
        request_payload = {
            "user_query": "Test query",
            "session_id": "test-session"
        }
        
        with patch("book_finder_agent.run.fetch_book_data") as mock_fetch:
            mock_fetch.return_value = (
                "Test response",
                [{"isbn": "123", "title": "Test Book"}],
                [{"text": "Citation 1"}],
                False
            )
            
            response = self.client.post(
                "/utility/book-content-rag-agent/prediction",
                data=json.dumps(request_payload),
                content_type="application/json"
            )
            
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.data)
            
            # Verify response structure
            required_keys = ["response", "agent_guide", "sources", "trace", "trace_root", "bypass_orchestrator_response"]
            for key in required_keys:
                self.assertIn(key, response_data)
            
            # Verify types
            self.assertIsInstance(response_data["response"], str)
            self.assertIsInstance(response_data["sources"], list)
            self.assertIsInstance(response_data["bypass_orchestrator_response"], bool)


if __name__ == "__main__":
    unittest.main()

