import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """
    Base configuration class for the Book Finder Agent.
    Loads all configuration from environment variables with sensible defaults.
    """
    
    # Flask Configuration
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Server Configuration
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    WORKERS = int(os.getenv('WORKERS', 4))
    
    # Google Cloud Configuration
    GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')
    GCP_CREDENTIALS_PATH = os.getenv('GCP_CREDENTIALS_PATH')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    # Database Configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 5432))
    DB_NAME = os.getenv('DB_NAME', 'book_finder_db')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', 20))
    DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', 10))
    DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', 3600))
    
    # Construct database connection string
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # Redis Configuration
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
    REDIS_POOL_SIZE = int(os.getenv('REDIS_POOL_SIZE', 10))
    
    # Construct Redis connection URL
    if REDIS_PASSWORD:
        REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    else:
        REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    
    # LLM Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    GOOGLE_GENAI_API_KEY = os.getenv('GOOGLE_GENAI_API_KEY')
    LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4')
    LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', 0.7))
    LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', 2048))
    
    # Semantic Search Configuration
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
    EMBEDDING_DIMENSIONS = int(os.getenv('EMBEDDING_DIMENSIONS', 1536))
    SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.3))
    FILTER_SIMILARITY_THRESHOLD = float(os.getenv('FILTER_SIMILARITY_THRESHOLD', 0.65))
    
    # Agent Configuration
    DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv('DEFAULT_SIMILARITY_THRESHOLD', 0.3))
    MAX_BOOKS_PER_RESPONSE = int(os.getenv('MAX_BOOKS_PER_RESPONSE', 3))
    BOOKS_PER_RESULT = int(os.getenv('BOOKS_PER_RESULT', 5))
    MAX_EXCERPTS_PER_BOOK = int(os.getenv('MAX_EXCERPTS_PER_BOOK', 5))
    MAX_BOOK_IDS = int(os.getenv('MAX_BOOK_IDS', 300))
    DEFAULT_SHOW_MORE_LENGTH = int(os.getenv('DEFAULT_SHOW_MORE_LENGTH', 3))
    MAX_SHOW_MORE_BOOKS = int(os.getenv('MAX_SHOW_MORE_BOOKS', 20))
    
    # Scoring Configuration
    CONTEXT_WEIGHT_SCORE = float(os.getenv('CONTEXT_WEIGHT_SCORE', 0.5))
    DOCUMENT_WEIGHT_SCORE = float(os.getenv('DOCUMENT_WEIGHT_SCORE', 0.2))
    KEYWORD_WEIGHT_SCORE = float(os.getenv('KEYWORD_WEIGHT_SCORE', 0.3))
    CHUNK_RETRIEVAL_DOCUMENT_BOOST = float(os.getenv('CHUNK_RETRIEVAL_DOCUMENT_BOOST', 0.2))
    
    # Database Table Names
    BOOK_TABLE = os.getenv('BOOK_TABLE', 'book_metadata_v2')
    BOOK_AUTHOR_TABLE = os.getenv('BOOK_AUTHOR_TABLE', 'book_author_v2')
    BOOK_AUTHOR_NORMALIZED_TABLE = os.getenv('BOOK_AUTHOR_NORMALIZED_TABLE', 'book_author_normalized')
    BOOK_GENRE_TABLE = os.getenv('BOOK_GENRE_TABLE', 'book_genre_v2')
    BOOK_AWARD_TABLE = os.getenv('BOOK_AWARD_TABLE', 'book_award_v2')
    BOOK_EXCERPT_TABLE = os.getenv('BOOK_EXCERPT_TABLE', 'book_excerpts_v2')
    BOOK_PUBLISHER_TABLE = os.getenv('BOOK_PUBLISHER_TABLE', 'book_publisher')
    CONTEXT_TABLE = os.getenv('CONTEXT_TABLE', 'book_retrieved_document_details')
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.getenv('LOG_FORMAT', 'json')
    GOOGLE_CLOUD_LOGGING = os.getenv('GOOGLE_CLOUD_LOGGING', 'True').lower() == 'true'
    
    # Session Configuration
    SESSION_EXPIRATION_DAYS = int(os.getenv('SESSION_EXPIRATION_DAYS', 30))
    SESSION_CLEANUP_INTERVAL_HOURS = int(os.getenv('SESSION_CLEANUP_INTERVAL_HOURS', 24))
    
    # API Configuration
    API_RATE_LIMIT = int(os.getenv('API_RATE_LIMIT', 100))
    API_TIMEOUT = int(os.getenv('API_TIMEOUT', 30))
    API_MAX_PAYLOAD_SIZE = int(os.getenv('API_MAX_PAYLOAD_SIZE', 10485760))
    
    # Feature Flags
    GENERATE_RESPONSE_FROM_DOCS = os.getenv('GENERATE_RESPONSE_FROM_DOCS', 'True').lower() == 'true'
    SMART_RESPONSE_ADJUSTMENT = os.getenv('SMART_RESPONSE_ADJUSTMENT', 'True').lower() == 'true'
    SHOW_HEADERS = os.getenv('SHOW_HEADERS', 'False').lower() == 'true'
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate critical configuration values.
        
        Returns:
            True if configuration is valid, raises exception otherwise
        """
        required_keys = [
            'GCP_PROJECT_ID',
            'DB_HOST',
            'DB_NAME',
            'OPENAI_API_KEY',
            'EMBEDDING_MODEL'
        ]
        
        missing_keys = [key for key in required_keys if not getattr(cls, key, None)]
        
        if missing_keys:
            logger.warning(
                f"Missing critical configuration values: {', '.join(missing_keys)}. "
                "Some features may not work correctly."
            )
            return False
        
        return True
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """
        Return configuration as a dictionary, excluding sensitive values.
        
        Returns:
            Dictionary of configuration values
        """
        sensitive_keys = {
            'SECRET_KEY', 'DB_PASSWORD', 'REDIS_PASSWORD',
            'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_GENAI_API_KEY',
            'GOOGLE_APPLICATION_CREDENTIALS'
        }
        
        config_dict = {}
        for key in dir(cls):
            if key.startswith('_') or callable(getattr(cls, key)):
                continue
            if key in sensitive_keys:
                config_dict[key] = '***REDACTED***'
            elif isinstance(getattr(cls, key), (str, int, float, bool)):
                config_dict[key] = getattr(cls, key)
        
        return config_dict


class DevelopmentConfig(Config):
    """
    Development environment configuration.
    Enables debug mode and uses local services.
    """
    FLASK_ENV = 'development'
    FLASK_DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """
    Production environment configuration.
    Optimized for security and performance.
    """
    FLASK_ENV = 'production'
    FLASK_DEBUG = False
    LOG_LEVEL = 'INFO'
    WORKERS = 8


class TestingConfig(Config):
    """
    Testing environment configuration.
    Uses in-memory databases and disables external services.
    """
    FLASK_ENV = 'testing'
    FLASK_DEBUG = True
    LOG_LEVEL = 'DEBUG'
    TESTING = True
    GOOGLE_CLOUD_LOGGING = False


def get_config(env: Optional[str] = None) -> Config:
    """
    Get configuration object based on environment.
    
    Args:
        env: Environment name ('development', 'production', 'testing').
             If None, reads from FLASK_ENV environment variable.
    
    Returns:
        Configuration object
    """
    env = env or os.getenv('FLASK_ENV', 'development')
    
    config_map = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig
    }
    
    config_class = config_map.get(env.lower(), DevelopmentConfig)
    logger.info(f"Loaded {config_class.__name__} configuration")
    
    return config_class

