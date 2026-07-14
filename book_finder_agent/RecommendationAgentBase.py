"""Base class for recommendation and retrieval agents.

Provides common lifecycle patterns, tool initialization, and error handling
for agents that combine semantic search, ranking, and LLM generation.
"""

import logging
import copy
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

from llm_studio_agents.AgentBase import AgentBase, AgentSetupBase


class RecommendationAgentBase(AgentBase, ABC):
    """Base class for retrieval and recommendation agents.
    
    Provides shared patterns for:
    - Tool initialization and configuration
    - Standard error handling
    - Trace management
    - Response tuple assembly
    
    Subclasses must implement:
    - CONFIG_CLASS: The Pydantic configuration schema
    - setup(): Tool initialization
    - run(): Main orchestration logic
    """
    
    CONFIG_CLASS = None  # Must be set by subclass
    
    def setup(
        self,
        config: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Initialize the agent.
        
        Args:
            config: Configuration dictionary containing tool configs
            data: Request data and context
            **kwargs: Additional arguments (e.g., agent_id, concierge_id)
            
        Returns:
            Dictionary with setup results
        """
        try:
            # Call parent setup to initialize config
            super().setup(config=config)
            
            # Store request data and metadata
            self.data = data or {}
            self.metadata = self.data.get("metadata", {})
            
            # Initialize observability
            self.error = None
            self.explainability_id = self.data.get("explainability_id", "")
            
            logging.info(
                f"{self.__class__.__name__} setup completed. "
                f"Config: {self.config.__class__.__name__}"
            )
            return {"status": "success", "message": "Agent setup completed"}
            
        except Exception as e:
            logging.error(f"Setup failed for {self.__class__.__name__}: {e}", exc_info=True)
            self.error = str(e)
            raise
    
    @abstractmethod
    def run(self, *args, **kwargs) -> tuple:
        """Main orchestration method.
        
        Must return a 4-tuple:
        (response_text: str, retrieved_documents: List, citations: List, bypass_orchestrator: bool)
        """
        pass
    
    def _save_tool_state(self, tool, attributes: List[str]) -> Dict[str, Any]:
        """Save mutable tool state for restoration after use.
        
        Args:
            tool: Tool instance
            attributes: List of attribute names to save
            
        Returns:
            Dictionary mapping attribute names to their current values
        """
        state = {}
        for attr in attributes:
            if hasattr(tool, attr):
                state[attr] = copy.deepcopy(getattr(tool, attr))
        return state
    
    def _restore_tool_state(self, tool, state: Dict[str, Any]):
        """Restore previously saved tool state.
        
        Args:
            tool: Tool instance
            state: Dictionary of attribute values to restore
        """
        for attr, value in state.items():
            if hasattr(tool, attr):
                setattr(tool, attr, copy.deepcopy(value))
    
    def _build_response_tuple(
        self,
        response_text: str,
        retrieved_documents: Optional[List] = None,
        citations: Optional[List] = None,
        bypass_orchestrator: bool = False
    ) -> tuple:
        """Build the standard 4-tuple response.
        
        Args:
            response_text: The agent's response text
            retrieved_documents: List of retrieved documents (default: empty list)
            citations: List of citation objects (default: empty list)
            bypass_orchestrator: Whether to bypass downstream processing (default: False)
            
        Returns:
            4-tuple: (response_text, documents, citations, bypass_flag)
        """
        return (
            response_text or "",
            retrieved_documents or [],
            citations or [],
            bool(bypass_orchestrator)
        )
    
    def _build_fallback_response(self, error_message: Optional[str] = None) -> tuple:
        """Build a safe fallback response when processing fails.
        
        Args:
            error_message: Optional error message to log
            
        Returns:
            4-tuple with fallback response
        """
        if error_message:
            logging.error(f"Building fallback response: {error_message}")
        
        fallback_text = getattr(
            self.config,
            'fallback_response',
            "I could not process your request at this time. Please try again."
        )
        
        return self._build_response_tuple(
            response_text=fallback_text,
            retrieved_documents=[],
            citations=[],
            bypass_orchestrator=True
        )
    
    @classmethod
    def get_setup_config(cls) -> Dict[str, Any]:
        """Get the configuration schema for this agent.
        
        Returns:
            Configuration schema dictionary
        """
        if cls.CONFIG_CLASS is None:
            raise NotImplementedError(
                f"{cls.__name__} must define CONFIG_CLASS attribute"
            )
        
        # This would be implemented in subclasses using the accumulator utility
        # from llm_studio_agents.utils.utils
        return cls.CONFIG_CLASS.model_json_schema()
    
    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM-specific configuration.
        
        Returns:
            LLM configuration dictionary
        """
        llm_config = {}
        
        # Extract LLM-related fields from config
        if hasattr(self.config, 'llm_model_name'):
            llm_config['model'] = self.config.llm_model_name
        if hasattr(self.config, 'llm_temperature'):
            llm_config['temperature'] = self.config.llm_temperature
        if hasattr(self.config, 'llm_max_tokens'):
            llm_config['max_tokens'] = self.config.llm_max_tokens
        if hasattr(self.config, 'llm_top_p'):
            llm_config['top_p'] = self.config.llm_top_p
        if hasattr(self.config, 'prompt_template'):
            llm_config['prompt_template'] = self.config.prompt_template
        
        return llm_config

