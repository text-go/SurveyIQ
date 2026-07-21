"""Agent state schema for the SurveyIQ LangGraph agent."""

from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


class AgentState(TypedDict):
    """State schema for the SurveyIQ agent graph.
    
    Tracks the full lifecycle of a user query through:
    parse → generate SQL → validate → execute → chart → narrate → respond
    """
    # Conversation messages (appended via add_messages reducer)
    messages: Annotated[list[AnyMessage], add_messages]
    
    # User's original natural language query
    user_query: str
    
    # Classified intent: "data_query", "insight", "comparison", "trend", "general"
    query_type: Optional[str]
    
    # Database schema context injected for SQL generation
    schema_context: Optional[str]
    
    # Generated SQL query
    generated_sql: Optional[str]
    
    # SQL validation result
    sql_valid: Optional[bool]
    sql_error: Optional[str]
    
    # Query execution results
    query_results: Optional[list[dict]]
    result_columns: Optional[list[str]]
    
    # Chart specification (Plotly JSON)
    chart_json: Optional[dict]
    chart_type: Optional[str]
    
    # Generated narrative text
    narrative: Optional[str]
    
    # Final combined response
    final_response: Optional[dict]
    
    # Error tracking and retry
    error: Optional[str]
    retry_count: int
    max_retries: int
    
    # Survey context
    survey_id: Optional[int]
