import os
import logging
import Config

from book_finder_agent import BookFinderAgent_v2
from llm_studio_agents.utils.templates.health_check import health_bp
from llm_studio_agents.utils.utils import process_config, get_setup_details, deep_update_dict
from llm_studio_agents.utils.agent_enums import input_enum
from ai_summary_utils import fetch_similar_reasoning

import google.cloud.logging

from flask import Flask, jsonify, request
from flask_cors import cross_origin


logging.getLogger().handlers = []
client = google.cloud.logging.Client()
client.setup_logging()

app = Flask(__name__)
app.json.sort_keys = False

PREFIX = "/utility/book-finder-agent"
AGENT_NAME = BookFinderAgent_v2

app.register_blueprint(health_bp, url_prefix=f'{PREFIX}/health')


@app.route(f'{PREFIX}/')
@cross_origin(supports_credentials=True)
def home():
    """Health check endpoint that returns agent name and status."""
    return f"{AGENT_NAME.__name__} is running!", 200


def prediction(data, trace):
    """
    Core prediction logic for the Book Finder Agent.
    Initializes the agent, loads configuration, and executes the run method.
    
    Args:
        data (dict): Input payload containing agent arguments and metadata
        trace (dict): Trace dictionary for logging execution details
    
    Returns:
        tuple: (response, retrieved_documents, citations, bypass_orchestrator_response)
    """
    rag_agent = AGENT_NAME()
    logging.info("######################### INPUT DATA #########################")
    logging.info(f"Input data: {data}")
    
    # Fetch or use provided configuration
    if data.get('agent_config', None):
        logging.info("Got the setup config from the input data payload")
        agent_config = data.get('agent_config')
    else:
        logging.info("Calling MongoDB to fetch the setup config")
        agent_config = get_setup_details(data['concierge_id'], data['agent_id'])
    
    if agent_config is None:
        raise Exception("Could not fetch setup config from MongoDB")
    
    # Override configuration if provided
    agent_settings = data.get(input_enum.AGENT_SETTINGS.value, {})
    override_section = agent_settings.get(input_enum.OVERRIDE_AGENT_CONFIG.value) or {}
    override_config = override_section.get(rag_agent.__class__.__name__)

    if override_config:
        logging.info("Overriding the config.")
        agent_config = deep_update_dict(agent_config, override_config)

    agent_config = process_config(config=agent_config, sub_level="tools")

    # Setup agent with configuration
    rag_agent.setup(config=agent_config, data=data, agent_id=data['agent_id'])

    next_trace = {}
    logging.info("Setup completed")
    
    # Execute agent run method
    response, retrieved_documents, citations, bypass_orchestrator_response = rag_agent.run(
        next_trace=next_trace, 
        trace=trace, 
        **data['agent_arguments']
    )
    
    return response, retrieved_documents, citations, bypass_orchestrator_response


@app.route(f'{PREFIX}/prediction', methods=['POST'])
@cross_origin(supports_credentials=True)
def predict_api():
    """
    POST endpoint for book finding predictions.
    Accepts JSON payload, processes it through the prediction function,
    and returns structured response with results, citations, and trace.
    """
    trace = {}
    try:
        data = request.get_json()
        
        if data is None:
            return jsonify({
                "error": "Invalid or missing JSON payload",
                "trace": trace,
                "trace_root": trace.pop('root', None)
            }), 400
        
        response, retrieved_documents, citations, bypass_orchestrator_response = prediction(data, trace)
        
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
            "trace_root": trace.pop('root', None),
            "bypass_orchestrator_response": bypass_orchestrator_response
        }), 200
        
    except Exception as e:
        logging.error(f"Error in prediction: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "trace": trace,
            "trace_root": trace.pop('root', None)
        }), 500


@app.route(f'{PREFIX}/get_config', methods=['GET'])
@cross_origin(supports_credentials=True)
def get_config_api():
    """
    GET endpoint to retrieve agent configuration schema.
    Returns the setup configuration for the Book Finder Agent.
    """
    try:
        response = AGENT_NAME.get_setup_config()
        if response:
            return jsonify(response), 200
        else:
            return jsonify({"message": "No configuration found"}), 204
    except Exception as e:
        logging.error(f"Error in get_config_api: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route(f'{PREFIX}/get_llm_config', methods=['GET'])
@cross_origin(supports_credentials=True)
def get_llm_config_api():
    """
    GET endpoint to retrieve LLM configuration.
    Returns the LLM configuration used by the Book Finder Agent.
    """
    try:
        agent = AGENT_NAME()
        response = agent.get_llm_config()
        if response:
            return jsonify(response), 200
        else:
            return jsonify({"message": "No LLM configuration found"}), 204
    except Exception as e:
        logging.error(f"Error in get_llm_config_api: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    """Application entry point for local development and testing."""
    app.run(debug=False, host='0.0.0.0', port=5000)

