from pydantic import Field
from typing import Optional, List, Dict, Any

from llm_studio_agents.AgentBase import AgentsTraceBase


class BookFinderAgentTrace(AgentsTraceBase):
    """
    Trace schema for BookFinderAgent execution observability and debugging.
    Captures all key inputs, intermediate artifacts, and outputs across pipeline phases.
    Fields marked with displayOnCard=True are surfaced in the frontend UI for debugging.
    """

    user_query: Optional[str] = Field(
        None,
        description="Original user query requesting book information.",
        title="User Query",
        displayOnCard=True,
    )
    
    active_filters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Active filter parameters applied to retrieval.",
        title="Active Filters",
        displayOnCard=True,
    )
    
    retrieved_books: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="List of books retrieved after semantic and filter-based search.",
        title="Retrieved Books",
        displayOnCard=False,
    )
    
    citations: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Verified citations extracted from LLM response, linked to source manuscripts.",
        title="Citations",
        displayOnCard=False,
    )
    
    final_response: Optional[str] = Field(
        None,
        description="Final LLM-generated response or structured book recommendations.",
        title="Final Response",
        displayOnCard=True,
    )
    
    error_state: Optional[str] = Field(
        None,
        description="Error message if execution failed; None if successful.",
        title="Error State",
        displayOnCard=True,
    )
    
    score_map: Optional[Dict[str, Dict[str, float]]] = Field(
        default_factory=dict,
        description="Per-book scoring breakdown showing semantic, document, and keyword scores.",
        title="Score Map",
        displayOnCard=False,
    )
    
    is_pagination_request: Optional[bool] = Field(
        False,
        description="Whether this request is a show-more pagination request.",
        title="Is Pagination",
        displayOnCard=True,
    )
    
    session_id: Optional[str] = Field(
        None,
        description="Session identifier for state persistence and pagination tracking.",
        title="Session ID",
        displayOnCard=False,
    )

