import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from llm_studio_agents.AgentBase import AgentBase, AgentSetupBase


class RecommendationAgentBase(AgentBase, ABC):
    """
    Abstract base class for recommendation-style agents.
    Provides a standard pipeline:
        1. retrieve IDs
        2. retrieve content
        3. post-process
        4. generate citations
    """

    CONFIG_CLASS = AgentSetupBase

    def __init__(self, config: Optional[Dict] = None, **kwargs):
        super().__init__(config=config, **kwargs)

    @abstractmethod
    def run(
        self, next_trace, trace, **kwargs
    ) -> dict:  # TODO: Enforce the kwargs to be 'user_query'
        pass

    @abstractmethod
    def _retrieve_ids(self, query: str, **kwargs):
        """
        Retrieve candidate IDs for recommendation.
        Example: fetch patent IDs, book IDs, or product IDs.
        """
        pass

    @abstractmethod
    def _retrieve_content(self, query: str, ids: List[str], **kwargs):
        """
        Retrieve detailed content for candidate IDs.
        Example: pull patent abstracts, book chapters, or product descriptions.
        """
        pass

    @abstractmethod
    def _post_process(self, content: List[Dict[str, Any]], **kwargs):
        """
        Clean, rank, deduplicate, or enrich retrieved content.
        Example: rank by relevance, filter expired items, summarize text.
        """
        pass

    @abstractmethod
    def _generate_citations(
        self, content: List[Dict[str, Any]], **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generate citations/references for the recommendations.
        Example: URLs, titles, metadata for display.
        """
        pass


    @classmethod
    @abstractmethod
    def get_setup_config(cls) -> dict:
        """
        Each recommendation agent must return its specific setup config schema.
        """
        pass