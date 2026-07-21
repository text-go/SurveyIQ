"""LangGraph StateGraph definition for the SurveyIQ AI agent.

Wires together all agent nodes into a directed graph with conditional routing:
  parse_query → [route by intent]
    → data_query/comparison/trend: generate_sql → validate_sql → execute → chart → narrate → respond
    → insight: insight_node → respond
    → general: general_node (terminal)
    
With retry loops: validate_sql ↔ generate_sql (max 3 retries)
"""

from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes import (
    parse_query_node, generate_sql_node, validate_sql_node,
    execute_query_node, build_chart_node, generate_narrative_node,
    insight_node, respond_node, error_node, general_node
)
from functools import partial


def route_by_intent(state: AgentState) -> str:
    """Route to the appropriate pipeline based on classified query intent."""
    query_type = state.get("query_type", "data_query")
    
    if query_type in ("data_query", "comparison", "trend"):
        return "generate_sql"
    elif query_type == "insight":
        return "insight"
    elif query_type == "general":
        return "general"
    else:
        return "generate_sql"


def route_after_validation(state: AgentState) -> str:
    """Route after SQL validation: proceed if valid, retry or error if not."""
    sql_valid = state.get("sql_valid", False)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if sql_valid:
        return "execute_query"
    elif retry_count < max_retries:
        return "generate_sql"  # retry with error context
    else:
        return "error"


def route_after_execution(state: AgentState) -> str:
    """Route after query execution: proceed if successful, retry or error if not."""
    error = state.get("error")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if error is None and state.get("query_results") is not None:
        return "build_chart"
    elif retry_count < max_retries:
        return "generate_sql"  # retry
    else:
        return "error"


def build_agent_graph(db_session, llm):
    """Build and compile the LangGraph StateGraph for the SurveyIQ agent.
    
    Args:
        db_session: SQLAlchemy AsyncSession for database access
        llm: LangChain LLM instance for text generation
        
    Returns:
        Compiled StateGraph ready for invocation
    """
    graph = StateGraph(AgentState)
    
    # Bind db and llm to each node via partial application
    graph.add_node("parse_query", partial(parse_query_node, db=db_session, llm=llm))
    graph.add_node("generate_sql", partial(generate_sql_node, db=db_session, llm=llm))
    graph.add_node("validate_sql", partial(validate_sql_node, db=db_session, llm=llm))
    graph.add_node("execute_query", partial(execute_query_node, db=db_session, llm=llm))
    graph.add_node("build_chart", partial(build_chart_node, db=db_session, llm=llm))
    graph.add_node("generate_narrative", partial(generate_narrative_node, db=db_session, llm=llm))
    graph.add_node("insight", partial(insight_node, db=db_session, llm=llm))
    graph.add_node("respond", partial(respond_node, db=db_session, llm=llm))
    graph.add_node("error", partial(error_node, db=db_session, llm=llm))
    graph.add_node("general", partial(general_node, db=db_session, llm=llm))
    
    # Set entry point
    graph.set_entry_point("parse_query")
    
    # Route from parse_query based on intent
    graph.add_conditional_edges(
        "parse_query",
        route_by_intent,
        {
            "generate_sql": "generate_sql",
            "insight": "insight",
            "general": "general"
        }
    )
    
    # SQL pipeline: generate → validate → execute → chart → narrate → respond
    graph.add_edge("generate_sql", "validate_sql")
    
    graph.add_conditional_edges(
        "validate_sql",
        route_after_validation,
        {
            "execute_query": "execute_query",
            "generate_sql": "generate_sql",  # retry
            "error": "error"
        }
    )
    
    graph.add_conditional_edges(
        "execute_query",
        route_after_execution,
        {
            "build_chart": "build_chart",
            "generate_sql": "generate_sql",  # retry
            "error": "error"
        }
    )
    
    graph.add_edge("build_chart", "generate_narrative")
    graph.add_edge("generate_narrative", "respond")
    
    # Insight pipeline: insight → respond
    graph.add_edge("insight", "respond")
    
    # Terminal nodes
    graph.add_edge("respond", END)
    graph.add_edge("error", END)
    graph.add_edge("general", END)
    
    return graph.compile()
