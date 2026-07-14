"""Semantic Similarity Tool for generating text embeddings.

This tool generates 1536-dimensional embeddings for text input using Google Vertex AI.
"""

import logging
from typing import Optional, List, Annotated
from pydantic import Field
import traceback

try:
    from google import genai
    from google.genai.types import EmbedContentConfig
    from google.oauth2 import service_account
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logging.warning("google-cloud-aiplatform or google-genai not installed; SemanticSimilarityTool will not function")

from llm_studio_agents.AgentBase import AgentSetupBase


class SemanticSimilarityToolSetup(AgentSetupBase):
    """Configuration schema for SemanticSimilarityTool."""
    
    embedding_model: Optional[str] = Field(
        default="text-embedding-004",
        description="Google Vertex AI embedding model name.",
        title="Embedding Model",
    )
    embedding_dimensions: Optional[int] = Field(
        default=1536,
        description="Dimension of embedding vectors (1536 for text-embedding-004).",
        title="Embedding Dimensions",
    )
    vertex_ai_location: Optional[str] = Field(
        default="us-central1",
        description="Google Cloud region for Vertex AI.",
        title="Vertex AI Location",
    )
    task_type: Optional[str] = Field(
        default="CLUSTERING",
        description="Task type for embedding (CLUSTERING, RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY).",
        title="Task Type",
    )


class SemanticSimilarityTool:
    """Tool for generating text embeddings using Google Vertex AI.
    
    This tool generates 1536-dimensional embeddings for text input,
    which are used for semantic similarity searches in vector databases.
    """
    
    CONFIG_CLASS = SemanticSimilarityToolSetup
    
    def __init__(self):
        """Initialize the tool."""
        self.config = None
        self.client = None
        self.project_id = None
        self.credentials = None
    
    def setup(self, config: dict, data: Optional[dict] = None) -> dict:
        """Initialize the Vertex AI client and store configuration.
        
        Args:
            config: Configuration dictionary with embedding settings
            data: Optional shared request data dictionary
            
        Returns:
            Empty dict on success
        """
        try:
            # Parse and validate configuration
            if isinstance(config, dict):
                self.config = SemanticSimilarityToolSetup(**config)
            else:
                self.config = config
            
            if not VERTEX_AI_AVAILABLE:
                logging.warning("Google Vertex AI libraries not available; embeddings will fail")
                return {}
            
            # Initialize Vertex AI client from environment credentials
            try:
                # Use default application credentials if available
                self.client = genai.Client()
                logging.info(f"Initialized SemanticSimilarityTool with model: {self.config.embedding_model}")
            except Exception as e:
                logging.warning(f"Failed to initialize Vertex AI client: {e}. Tool will fail at runtime.")
                self.client = None
            
            return {}
            
        except Exception as e:
            logging.error(f"Error in SemanticSimilarityTool.setup: {e}", exc_info=True)
            return {}
    
    def run(
        self,
        text: Annotated[str, "Text to generate embedding for."],
        next_trace: Optional[dict] = None,
        trace: Optional[dict] = None,
    ) -> Optional[List[float]]:
        """Generate embedding for input text.
        
        Args:
            text: Input text to embed
            next_trace: Optional trace dictionary for nested observability
            trace: Optional trace dictionary for nested observability
            
        Returns:
            List of floats representing the embedding vector, or None on failure
        """
        if not text or not isinstance(text, str):
            logging.warning("SemanticSimilarityTool.run: Invalid input text")
            return None
        
        if self.client is None or not VERTEX_AI_AVAILABLE:
            logging.error("SemanticSimilarityTool: Client not initialized; cannot generate embeddings")
            return None
        
        try:
            # Call Vertex AI embedding API
            response = self.client.models.embed_content(
                model=self.config.embedding_model,
                contents=text.strip(),
                config=EmbedContentConfig(
                    output_dimensionality=self.config.embedding_dimensions,
                    task_type=self.config.task_type
                )
            )
            
            # Extract embedding vector
            if response and response.embeddings and len(response.embeddings) > 0:
                embedding_vector = response.embeddings[0].values
                logging.debug(f"Generated embedding of dimension {len(embedding_vector)} for text: {text[:100]}...")
                return list(embedding_vector)
            else:
                logging.warning("Vertex AI returned empty embedding response")
                return None
                
        except Exception as e:
            logging.error(f"Error generating embedding in SemanticSimilarityTool.run: {e}", exc_info=True)
            return None

