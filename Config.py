import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration with environment variable support."""
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database Configuration
    DATABASE_URI = os.getenv('DATABASE_URI', 'postgresql://user:password@localhost:5432/bookfinder_db')
    
    # Gunicorn Worker Configuration
    WORKER_COUNT = int(os.getenv('WORKER_COUNT', 4))
    WORKER_TIMEOUT = int(os.getenv('WORKER_TIMEOUT', 120))
    WORKER_THREADS_COUNT = int(os.getenv('WORKER_THREADS_COUNT', 2))
    WORKER_GRACEFUL_TIMEOUT = int(os.getenv('WORKER_GRACEFUL_TIMEOUT', 30))
    MAX_REQUEST_TO_WORKER_RESTART = int(os.getenv('MAX_REQUEST_TO_WORKER_RESTART', 1000))
    
    # Server Configuration
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5002))
    
    # Google Cloud Configuration
    GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID', '')
    GCP_REGION = os.getenv('GCP_REGION', 'us-central1')
    
    # LLM Configuration
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'google')  # google, openai, anthropic
    LLM_MODEL = os.getenv('LLM_MODEL', 'gemini-2.0-flash')
    LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', 0.7))
    LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', 2048))
    
    # Embedding Configuration
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-004')
    EMBEDDING_DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', 768))
    
    # Redis Configuration (for caching and session management)
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Retrieval Configuration
    MAX_RESULTS_PER_QUERY = int(os.getenv('MAX_RESULTS_PER_QUERY', 10))
    SEMANTIC_SIMILARITY_THRESHOLD = float(os.getenv('SEMANTIC_SIMILARITY_THRESHOLD', 0.65))
    CITATION_CONFIDENCE_THRESHOLD = float(os.getenv('CITATION_CONFIDENCE_THRESHOLD', 0.7))
    
    # Pagination Configuration
    PAGE_SIZE = int(os.getenv('PAGE_SIZE', 5))
    SHOW_MORE_BATCH_SIZE = int(os.getenv('SHOW_MORE_BATCH_SIZE', 5))
    
    # Session Configuration
    SESSION_EXPIRY_HOURS = int(os.getenv('SESSION_EXPIRY_HOURS', 24))
    
    # Feature Toggles
    ENABLE_SEMANTIC_SEARCH = os.getenv('ENABLE_SEMANTIC_SEARCH', 'true').lower() == 'true'
    ENABLE_EXACT_MATCH_FILTER = os.getenv('ENABLE_EXACT_MATCH_FILTER', 'true').lower() == 'true'
    ENABLE_LLM_GENERATION = os.getenv('ENABLE_LLM_GENERATION', 'true').lower() == 'true'
    ENABLE_CITATION_GENERATION = os.getenv('ENABLE_CITATION_GENERATION', 'true').lower() == 'true'
    
    # Book Database Table Mapping
    BOOK_SUMMARY_TABLE = os.getenv('BOOK_SUMMARY_TABLE', 'book_summaries')
    BOOK_DETAILS_TABLE = os.getenv('BOOK_DETAILS_TABLE', 'book_details')
    GENRE_TABLE = os.getenv('GENRE_TABLE', 'genres')
    AUTHOR_TABLE = os.getenv('AUTHOR_TABLE', 'authors')
    CONTRIBUTOR_TABLE = os.getenv('CONTRIBUTOR_TABLE', 'contributors')
    QUOTE_TABLE = os.getenv('QUOTE_TABLE', 'quotes')
    CHARACTER_TABLE = os.getenv('CHARACTER_TABLE', 'characters')
    LOCATION_TABLE = os.getenv('LOCATION_TABLE', 'locations')
    PRIZE_TABLE = os.getenv('PRIZE_TABLE', 'prizes')
    PUBLISHER_TABLE = os.getenv('PUBLISHER_TABLE', 'publishers')
    SECTION_TABLE = os.getenv('SECTION_TABLE', 'sections')
