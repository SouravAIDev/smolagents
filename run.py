import os
import logging

from config import Config
from agents.book_finder_agent.book_finder_agent import BookFinderAgent
from book_finder_helpers import InputValidationError
from llm_studio_agents.utils.templates.health_check import health_bp
from llm_studio_agents.utils.utils import process_config, get_setup_details, deep_update_dict
from llm_studio_agents.utils.agent_enums import input_enum

import google.cloud.logging

from flask import Flask, jsonify, request
from flask_cors import cross_origin


logging.getLogger().handlers = []
client = google.cloud.logging.Client()
client.setup_logging()

app = Flask(__name__)
app.json.sort_keys = False

PREFIX = "/utility/book-finder-agent"
AGENT_NAME = BookFinderAgent

app.register_blueprint(health_bp, url_prefix=f'{PREFIX}/health')

@app.route(f'{PREFIX}/')
@cross_origin(supports_credentials=True)
def home():
    return f"{AGENT_NAME.__name__} is running!", 200


def prediction(data, trace):
    rag_agent = AGENT_NAME()
    logging.info("######################### INPUT DATA #########################")
    logging.info(f"Input data: {data}")
    if data.get('agent_config', None):
        logging.info("Got the setup config from the input data payload")
        agent_config = data.get('agent_config')
    else:
        logging.info("Calling configuration store to fetch the setup config")
        agent_config = get_setup_details(data['concierge_id'], data['agent_id'])
    
    if agent_config is None:
        raise Exception("Could not fetch setup config")
    
    agent_settings = data.get(input_enum.AGENT_SETTINGS.value, {})
    override_section = agent_settings.get(input_enum.OVERRIDE_AGENT_CONFIG.value) or {}
    override_config = override_section.get(rag_agent.__class__.__name__)

    if override_config:
        logging.info("Overriding the config.")
        agent_config = deep_update_dict(agent_config, override_config)

    agent_config = process_config(config=agent_config, sub_level="tools")

    rag_agent.setup(config=agent_config, data=data, agent_id=data['agent_id'])

    next_trace = {}
    logging.info("Setup completed")
    try:
        response, retrieved_documents, citations, bypass_orchestrator_response = rag_agent.run(next_trace=next_trace, trace=trace, **data['agent_arguments'])
        return response, retrieved_documents, citations, bypass_orchestrator_response
    except InputValidationError as e:
        logging.error(f"Input validation error: {e}")
        raise  # Propagate to predict_api handler for HTTP 400 response


@app.route(f'{PREFIX}/prediction', methods=['POST'])
@cross_origin(supports_credentials=True)
def predict_api():
    trace = {}
    try:
        data = request.get_json()
        response, retrieved_documents, citations, bypass_orchestrator_response = prediction(data, trace)
        agent_guide = None
        if retrieved_documents:
            agent_guide = {
                "retrieved_documents": retrieved_documents,
            }

        return jsonify({"response": response, "agent_guide":agent_guide, "sources":citations, "trace": trace, "trace_root": trace.pop('root', None), "bypass_orchestrator_response":bypass_orchestrator_response}), 200
    except InputValidationError as e:
        logging.error(f"Input validation error: {e}")
        return jsonify({"error": str(e), "error_type": "validation_error", "trace": trace, "trace_root": trace.pop('root', None)}), 400
    except Exception as e:
        logging.error(f"Error in prediction: {e}")
        return jsonify({"error": str(e), "trace": trace, "trace_root": trace.pop('root', None)}), 500


@app.route(f'{PREFIX}/get_config', methods=['GET'])
@cross_origin(supports_credentials=True)
def get_config_api():
    try:
        response = AGENT_NAME.get_setup_config()
        if response:
            return jsonify(response), 200
        else:
            return jsonify({"message": "No configuration found"}), 204
    except Exception as e:
        logging.info(f"Error in get_config_api: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route(f'{PREFIX}/get_llm_config', methods=['GET'])
@cross_origin(supports_credentials=True)
def get_llm_config_api():
    try:
        response = AGENT_NAME().get_llm_config()
        if response:
            return jsonify(response), 200
        else:
            return jsonify({"message": "No LLM configuration found"}), 204
    except Exception as e:
        logging.info(f"Error in get_llm_config_api: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    gunicorn_command = (
        f"gunicorn --workers {Config.WORKER_COUNT} --worker-class gthread --bind 0.0.0.0:5002 "
        f"--timeout {Config.WORKER_TIMEOUT} --keep-alive 120 --max-requests {Config.MAX_REQUEST_TO_WORKER_RESTART} --max-requests-jitter 50 "
        f"--log-level info --threads {Config.WORKER_THREADS_COUNT} --access-logfile - --error-logfile - "
        f"--graceful-timeout {Config.WORKER_GRACEFUL_TIMEOUT} --limit-request-line 8190 run:app"
    )
    
    os.system(gunicorn_command)
