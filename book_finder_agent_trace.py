from pydantic import Field
from typing import Optional, List, Dict, Any

from llm_studio_agents.AgentBase import AgentsTraceBase


class BookFinderAgentTrace(AgentsTraceBase):
    """Trace schema for capturing Book Finder Agent execution details for observability and debugging."""
    
    response: str = Field(..., description="LLM response for the request.")
    fallback_response: str = Field(
        ..., description="Default response when no suitable answer can be generated."
    )
    show_headers: Optional[bool] = Field(
        ..., description="Whether to show thinking steps for this agent."
    )
    smart_response_adjustment: Optional[bool] = Field(
        ..., description="Toggle to enable/disable prompt adjustments."
    )
    filters: Dict[str, str] = Field(
        ...,
        description="Filters applied to the book search",
        title="Applied Filters",
        displayOnCard=True
    )
    target: str = Field(
        ...,
        description="Target based on the user query",
        title="Target",
        displayOnCard=True
    )
    user_query: str = Field(
        ...,
        description="Input query for the book finder agent",
        title="Input Query",
        displayOnCard=True
    )
    is_intersection: bool = Field(
        ...,
        description="Whether intersection logic was used for filtering",
        title="Is Intersection",
        displayOnCard=True
    )
    retrieved_for_llm: Optional[Dict] = Field(
        ...,
        description="Context sent to the LLM for generating response",
        title="LLM context"
    )
    citations: List[Dict] = Field(
        ...,
        description="List of citations for the book content excerpts retrieved.",
        title="Citations"
    )
    error: str = Field(
        ...,
        description="Error message if any exception occurred during processing.",
        title="Error Message"
    )
    score_map: Dict[str, Dict] = Field(
        ...,
        description="Mapping of book IDs to similarity and document scores",
        title="Score Map",
    )

