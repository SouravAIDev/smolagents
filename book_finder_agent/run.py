import os
import logging
from flask import Flask, request, jsonify, Blueprint
from flask_cors import cross_origin
from dotenv import load_dotenv
from pydantic import ValidationError

from book_finder_agent.book_finder_helpers import (
    validate_request,
    BookFinderRequestSchema,
    FILTER_TABLE_MAPPING as BOOK_FILTER_TABLE_MAPPING,
)
from book_finder_agent.book_finder_agent import BookFinderAgent
from llm_studio_agents.utils.utils import process_config, get_setup_details, deep_update_dict
from llm_studio_agents.utils.agent_enums import input_enum

# Initialize Flask app
app = Flask(__name__)
app.json.sort_keys = False

# Service configuration
PREFIX = "/utility/book-content-rag-agent"
HEALTH_CHECK_PREFIX = f"{PREFIX}/health"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""
    pass


def setup(app_instance: Flask) -> None:
    """
    Initialize the Flask application with configuration and shared resources.
    
    Args:
        app_instance: Flask application instance to configure
        
    Raises:
        ConfigurationError: If required environment variables are missing
    """
    global app
    app = app_instance
    
    # Load database connection URI from environment
    database_uri = os.getenv("DATABASE_URI")
    if not database_uri:
        raise ConfigurationError("DATABASE_URI environment variable is not set")
    
    secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    
    # Configure Flask app
    app.config.from_mapping(
        SECRET_KEY=secret_key,
        DATABASE_URI=database_uri,
        JSON_SORT_KEYS=False
    )
    
    # Register book domain filter table mapping from helpers module
    # This is used by downstream retrieval stages for database query routing
    app.config["BOOK_FILTER_TABLE_MAPPING"] = BOOK_FILTER_TABLE_MAPPING
    
    logger.info("Book Finder Agent setup complete. Database: %s", database_uri[:50] + "...")


# ============================================================================
# STEP A2: Application Bootstrap & Service Registration
# ============================================================================

def register_routes(app_instance: Flask) -> None:
    """
    Register all Flask route handlers for the Book Finder Agent.
    This is the primary entry point for HTTP requests.
    
    Args:
        app_instance: Flask application instance to register routes on
    """
    
    @app_instance.route(f"{PREFIX}/", methods=["GET"])
    @cross_origin(supports_credentials=True)
    def home():
        """
        Root route - returns a simple status message confirming the agent is running.
        Used for manual health checks and debugging.
        """
        return "Book Finder Agent is running!", 200
    
    @app_instance.route(f"{PREFIX}/prediction", methods=["POST"])
    @cross_origin(supports_credentials=True)
    def predict_api():
        """
        Main prediction endpoint (Step A2 → A3 → A4 → A5).
        Handles incoming HTTP requests and routes them through the orchestration pipeline.
        
        Returns:
            JSON response with structure:
            {
                "response": str,  # Final LLM-generated response
                "agent_guide": {...},  # Retrieved documents metadata
                "sources": [...],  # Citation objects
                "trace": {...},  # Execution trace data
                "trace_root": None,  # Trace root reference
                "bypass_orchestrator_response": bool  # Flag for downstream processing
            }
        """
        trace = {}
        try:
            # Step A2.1: Extract JSON payload from HTTP request
            data = request.get_json()
            
            if data is None:
                logger.warning("Received request with no JSON payload")
                return jsonify({"error": "Request body must be valid JSON"}), 400
            
            logger.info("Received prediction request with payload keys: %s", list(data.keys()))
            
            # ===== Step A3: Request Validation & Input Normalization =====
            # Validate and normalize incoming request payload
            # Enforces required fields (user_query, session_id) and normalizes optional fields
            try:
                validated_request: BookFinderRequestSchema = validate_request(data)
                logger.info(f"Step A3 complete: Request validated. Session: {validated_request.session_id}")
            except ValidationError as validation_err:
                logger.warning(f"Step A3 failed: Request validation error: {validation_err.errors()}")
                return jsonify({
                    "error": "Request validation failed",
                    "details": validation_err.errors()
                }), 400
            
            # Step A3.1: Determine execution branch (pagination vs. fresh query)
            is_show_more = validated_request.is_pagination_request()
            logger.info(f"Step A3.1 complete: Execution branch determined. IsShowMore: {is_show_more}")
            
            # ===== Step A4-A5: Delegate to prediction logic =====
            # Pass validated request to downstream orchestration
            response, retrieved_documents, citations, bypass_flag = fetch_book_data(
                validated_request=validated_request, trace=trace
            )
            
            # Step A2.3: Format response according to standard contract
            agent_guide = None
            if retrieved_documents:
                agent_guide = {
                    "retrieved_documents": retrieved_documents,
                }
            
            return jsonify({
                "response": response,
                "agent_guide": agent_guide,
                "sources": citations,
                "trace": trace,
                "trace_root": trace.pop("root", None),
                "bypass_orchestrator_response": bypass_flag
            }), 200
            
        except Exception as e:
            logger.error(f"Error in prediction endpoint: {str(e)}", exc_info=True)
            return jsonify({
                "error": str(e),
                "trace": trace,
                "trace_root": trace.pop("root", None)
            }), 500
    
    @app_instance.route(f"{PREFIX}/get_config", methods=["GET"])
    @cross_origin(supports_credentials=True)
    def get_config_api():
        """
        Configuration introspection endpoint.
        Returns the agent's full configuration schema for UI building and documentation.
        """
        try:
            # This will be populated when BookFinderAgent is created in later ACTs
            response = {"message": "Configuration endpoint - implementation pending"}
            return jsonify(response), 200
        except Exception as e:
            logger.error(f"Error in get_config endpoint: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500
    
    @app_instance.route(f"{PREFIX}/get_llm_config", methods=["GET"])
    @cross_origin(supports_credentials=True)
    def get_llm_config_api():
        """
        LLM-specific configuration endpoint.
        Returns only the LLM-related configuration for tooling that cares about model settings.
        """
        try:
            # This will be populated when BookFinderAgent is created in later ACTs
            response = {"message": "LLM config endpoint - implementation pending"}
            return jsonify(response), 200
        except Exception as e:
            logger.error(f"Error in get_llm_config endpoint: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500
    
    logger.info("Routes registered successfully on prefix: %s", PREFIX)


def fetch_book_data(validated_request: BookFinderRequestSchema, trace: dict) -> tuple:
    """
    Orchestrates the book retrieval pipeline (Steps A4-A5: Core Processing & Content Retrieval).
    
    This is the complete orchestration layer that routes validated requests through the
    BookFinderAgent, manages tool configuration, handles errors gracefully, and returns
    a properly formatted 4-tuple response conforming to the LLM Studio contract.
    
    Args:
        validated_request: BookFinderRequestSchema instance (output from Step A3 validation)
        trace: Execution trace object to be populated during execution
        
    Returns:
        Tuple of (response_text, retrieved_documents, citations, bypass_flag)
    """
    try:
        # Log validated request for traceability
        logger.info(
            f"fetch_book_data called (Steps A4-A5): Query='{validated_request.user_query[:50]}...', "
            f"Session={validated_request.session_id}, IsShowMore={validated_request.is_pagination_request()}"
        )
        
        # Step A4.1: Prepare agent instance and request data
        agent = BookFinderAgent()
        
        # Prepare data dictionary from validated request
        data = {
            "question": validated_request.user_query,
            "session_id": validated_request.session_id,
            "chat_history": [],  # TODO: Load from session store if pagination enabled
            "metadata": "{}",  # Placeholder for metadata JSON
        }
        
        # Step A4.2: Resolve agent configuration
        # Try to get configuration from inline config first, then from MongoDB if available
        agent_config = None
        
        # Check if agent_config is provided inline in the request
        if hasattr(validated_request, 'agent_config') and validated_request.agent_config:
            logger.info("Using agent configuration from request payload")
            agent_config = validated_request.agent_config
        else:
            # In production, fetch from MongoDB or configuration store
            # For now, use default configuration
            try:
                # TODO: Call get_setup_details if concierge_id and agent_id are available
                logger.info("Using default agent configuration")
                agent_config = BookFinderAgent.get_setup_config()
            except Exception as e:
                logger.warning(f"Failed to fetch agent config: {e}. Using defaults.")
                agent_config = BookFinderAgent.get_setup_config()
        
        if not agent_config:
            logger.error("Failed to resolve agent configuration")
            return (
                "Unable to load agent configuration. Please try again.",
                [],
                [],
                False
            )
        
        # Step A4.3: Handle configuration overrides
        # Support per-request configuration overrides via the agent_settings mechanism
        if hasattr(validated_request, 'agent_settings') and validated_request.agent_settings:
            override_section = validated_request.agent_settings.get("override_agent_config", {})
            override_config = override_section.get(BookFinderAgent.__name__)
            if override_config:
                logger.info("Applying per-request configuration overrides")
                agent_config = deep_update_dict(agent_config, override_config)
        
        # Step A4.4: Process configuration through LLM Studio utility
        # This hydrates nested tool configurations
        agent_config = process_config(config=agent_config, sub_level="tools")
        
        # Step A4.5: Initialize agent with configuration and request data
        logger.info("Initializing BookFinderAgent")
        agent.setup(config=agent_config, data=data)
        
        # Step A4.6: Extract filter arguments from validated request
        filter_kwargs = {}
        if validated_request.filters:
            filters_dict = validated_request.get_filters_dict()
            filter_kwargs = filters_dict
        
        # Step A4.7: Prepare run() method arguments
        run_arguments = {
            "user_query": validated_request.user_query,
            "show_more_details": validated_request.show_more_details,
            **filter_kwargs,  # Unpack individual filter parameters
        }
        
        # Step A5: Execute agent run() method (Core Processing & Content Retrieval)
        logger.info(f"Executing BookFinderAgent.run() with arguments: {list(run_arguments.keys())}")
        next_trace = {}
        response_data = agent.run(
            next_trace=next_trace,
            trace=trace,
            **run_arguments
        )
        
        # Step A5.1: Unpack response tuple from agent
        if isinstance(response_data, dict):
            response_text = response_data.get("response_text", "No response generated")
            retrieved_books = response_data.get("retrieved_books", [])
            citations = response_data.get("citations", [])
            bypass_flag = response_data.get("bypass_orchestrator_response", False)
        else:
            # Fallback if unexpected response format
            logger.warning(f"Unexpected response format from agent: {type(response_data)}")
            response_text = "Unexpected agent response format"
            retrieved_books = []
            citations = []
            bypass_flag = False
        
        logger.info(f"Agent execution complete. Retrieved {len(retrieved_books)} books, {len(citations)} citations")
        
        return (
            response_text,
            retrieved_books,
            citations,
            bypass_flag
        )
        
    except Exception as e:
        logger.error(f"Error in fetch_book_data orchestration: {str(e)}", exc_info=True)
        return (
            "An unexpected error occurred while processing your request. Please try again.",
            [],
            [],
            False
        )


def create_health_check_blueprint() -> Blueprint:
    """
    Create the health check blueprint for liveness/readiness probes.
    Container orchestration platforms use this endpoint to determine service readiness.
    
    Returns:
        Blueprint configured with health check route
    """
    health_bp = Blueprint("health", __name__)
    
    @health_bp.route("/", methods=["GET"])
    def health_check():
        """
        Health check endpoint - returns 200 if service is ready.
        Should reflect real readiness, not just "the process is up".
        """
        try:
            # TODO: In production, add checks for database connectivity
            # and other critical dependencies here
            return jsonify({"status": "healthy"}), 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return jsonify({"status": "unhealthy", "error": str(e)}), 503
    
    return health_bp


if __name__ == "__main__":
    # Setup application on startup
    setup(app)
    
    # Register health check blueprint at designated prefix
    health_bp = create_health_check_blueprint()
    app.register_blueprint(health_bp, url_prefix=f"{PREFIX}/health")
    
    # Register main API routes
    register_routes(app)
    
    # Development server (do not use in production - see Docker/Gunicorn configuration)
    # For production deployment, use Gunicorn as specified in the Dockerfile
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting Book Finder Agent on port {port}")
    app.run(debug=False, host="0.0.0.0", port=port)

