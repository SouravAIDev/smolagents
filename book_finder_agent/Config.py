"""Configuration management for Book Finder Agent.

Loads environment variables and provides centralized configuration
for database connections, Google Cloud services, and deployment settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ConfigError(Exception):
    """Raised when required configuration is missing."""
    pass


# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
POSTGRES_DB = os.getenv('POSTGRES_DB', 'book_finder')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')

DATABASE_URI = os.getenv(
    'DATABASE_URI',
    f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'
)

# ============================================================================
# GOOGLE CLOUD CONFIGURATION
# ============================================================================

GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
PUBSUB_PROJECT_ID = os.getenv('PUBSUB_PROJECT_ID', 'book-finder-project')
GCLOUD_LOCATION = os.getenv('GCLOUD_LOCATION', 'us-central1')

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================

PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# ============================================================================
# GUNICORN DEPLOYMENT CONFIGURATION
# ============================================================================

WORKER_COUNT = int(os.getenv('WORKER_COUNT', 4))
WORKER_TIMEOUT = int(os.getenv('WORKER_TIMEOUT', 120))
MAX_REQUEST_TO_WORKER_RESTART = int(os.getenv('MAX_REQUEST_TO_WORKER_RESTART', 1000))
WORKER_THREADS_COUNT = int(os.getenv('WORKER_THREADS_COUNT', 4))
WORKER_GRACEFUL_TIMEOUT = int(os.getenv('WORKER_GRACEFUL_TIMEOUT', 30))

# ============================================================================
# LLM CONFIGURATION
# ============================================================================

LLM_MODEL_NAME = os.getenv('LLM_MODEL_NAME', 'gemini-2.0-flash-001')
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', 0.7))
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', 1024))
LLM_TOP_P = float(os.getenv('LLM_TOP_P', 0.95))

# ============================================================================
# RETRIEVAL CONFIGURATION
# ============================================================================

MAX_BOOK_IDS = int(os.getenv('MAX_BOOK_IDS', 300))
DEFAULT_SHOW_MORE_LENGTH = int(os.getenv('DEFAULT_SHOW_MORE_LENGTH', 3))
MAX_SHOW_MORE_BOOKS = int(os.getenv('MAX_SHOW_MORE_BOOKS', 20))
MAX_CHUNKS_PER_BOOK = int(os.getenv('MAX_CHUNKS_PER_BOOK', 3))
MAX_CHUNKS_TO_USE = int(os.getenv('MAX_CHUNKS_TO_USE', 6))
BOOKS_PER_RESULT = int(os.getenv('BOOKS_PER_RESULT', 5))
MAX_BOOKS_PER_RESPONSE = int(os.getenv('MAX_BOOKS_PER_RESPONSE', 3))

# ============================================================================
# SIMILARITY THRESHOLDS
# ============================================================================

SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.3))
FILTER_SIMILARITY_THRESHOLD = float(os.getenv('FILTER_SIMILARITY_THRESHOLD', 0.65))

# ============================================================================
# SCORING WEIGHTS
# ============================================================================

CONTEXT_WEIGHT_SCORE = float(os.getenv('CONTEXT_WEIGHT_SCORE', 0.45))
DOCUMENT_WEIGHT_SCORE = float(os.getenv('DOCUMENT_WEIGHT_SCORE', 0.25))
KEYWORD_WEIGHT_SCORE = float(os.getenv('KEYWORD_WEIGHT_SCORE', 0.30))

# ============================================================================
# DATABASE TABLE NAMES
# ============================================================================

BOOK_SUMMARY_TABLE = os.getenv('BOOK_SUMMARY_TABLE', 'book_summary_backup_2')
BOOK_METADATA_TABLE = os.getenv('BOOK_METADATA_TABLE', 'book_metadata_backup_2')
BOOK_CONTENT_TABLE = os.getenv('BOOK_CONTENT_TABLE', 'book_content_chunked_backup_2')
BOOK_CONTRIBUTORS_TABLE = os.getenv('BOOK_CONTRIBUTORS_TABLE', 'book_contributors_backup_2')
BOOK_CHARACTERS_TABLE = os.getenv('BOOK_CHARACTERS_TABLE', 'book_notable_characters_backup_2')
BOOK_QUOTES_TABLE = os.getenv('BOOK_QUOTES_TABLE', 'book_notable_quotes_backup_2')
BOOK_AUDIENCE_TABLE = os.getenv('BOOK_AUDIENCE_TABLE', 'book_audience_backup_2')
BOOK_LOCATIONS_TABLE = os.getenv('BOOK_LOCATIONS_TABLE', 'geo_location_backup_2')
BOOK_SECTIONS_TABLE = os.getenv('BOOK_SECTIONS_TABLE', 'book_content_sections_backup_2')
BOOK_PUBLISHERS_TABLE = os.getenv('BOOK_PUBLISHERS_TABLE', 'book_publishers_backup_2')
BOOK_IMPRINT_TABLE = os.getenv('BOOK_IMPRINT_TABLE', 'book_imprint_details_backup_2')
BOOK_PRIZES_TABLE = os.getenv('BOOK_PRIZES_TABLE', 'book_prize_details_backup_2')
SESSION_CONTEXT_TABLE = os.getenv('SESSION_CONTEXT_TABLE', 'book_retrieved_document_details')

# ============================================================================
# CITATION & VERIFICATION
# ============================================================================

MAX_WORKERS_FOR_CITATION_GENERATION = int(os.getenv('MAX_WORKERS_FOR_CITATION_GENERATION', 10))
CITATION_RETRY_COUNT = int(os.getenv('CITATION_RETRY_COUNT', 1))

# ============================================================================
# FEATURE FLAGS
# ============================================================================

GENERATE_RESPONSE_FROM_DOCS = os.getenv('GENERATE_RESPONSE_FROM_DOCS', 'False').lower() == 'true'
SHOW_HEADERS = os.getenv('SHOW_HEADERS', 'False').lower() == 'true'
SMART_RESPONSE_ADJUSTMENT = os.getenv('SMART_RESPONSE_ADJUSTMENT', 'True').lower() == 'true'
ENABLE_STREAMING = os.getenv('ENABLE_STREAMING', 'True').lower() == 'true'

# ============================================================================
# VALIDATION
# ============================================================================

def validate_configuration():
    """Validate that all required configuration is present.
    
    Raises:
        ConfigError: If critical configuration is missing.
    """
    critical_vars = [
        ('POSTGRES_HOST', POSTGRES_HOST),
        ('POSTGRES_DB', POSTGRES_DB),
        ('POSTGRES_USER', POSTGRES_USER),
        ('PUBSUB_PROJECT_ID', PUBSUB_PROJECT_ID),
    ]
    
    missing = [name for name, value in critical_vars if not value]
    if missing:
        raise ConfigError(
            f"Missing required configuration variables: {', '.join(missing)}"
        )
    
    # Validate score weights sum to 1.0
    total_weight = CONTEXT_WEIGHT_SCORE + DOCUMENT_WEIGHT_SCORE + KEYWORD_WEIGHT_SCORE
    if not (0.99 <= total_weight <= 1.01):  # Allow for floating point precision
        raise ConfigError(
            f"Scoring weights must sum to 1.0 (got {total_weight}). "
            f"Current values: CONTEXT={CONTEXT_WEIGHT_SCORE}, "
            f"DOCUMENT={DOCUMENT_WEIGHT_SCORE}, KEYWORD={KEYWORD_WEIGHT_SCORE}"
        )


# Perform validation on import
if not DEBUG:
    try:
        validate_configuration()
    except ConfigError as e:
        import logging
        logging.error(f"Configuration validation failed: {e}")
        raise

