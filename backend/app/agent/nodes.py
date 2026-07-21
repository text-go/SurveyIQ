"""LangGraph agent node functions for the SurveyIQ pipeline.

Each node is an async function that takes AgentState and returns a partial state update.
Nodes: parse_query → generate_sql → validate_sql → execute_query → build_chart → generate_narrative → respond
"""

import json
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.agent.state import AgentState
from app.agent.prompts import (
    SYSTEM_PROMPT, SQL_GENERATION_PROMPT, CLASSIFY_PROMPT,
    NARRATIVE_PROMPT, FEW_SHOT_EXAMPLES
)
from app.agent.tools import (
    get_database_schema, validate_sql as validate_sql_tool,
    execute_query as execute_query_tool,
    auto_select_chart, build_chart_from_results,
    get_sentiment_summary, get_themes_summary
)


async def parse_query_node(state: AgentState, db, llm) -> dict:
    """Classify the user's query intent and fetch schema context."""
    user_query = state["user_query"]
    
    # Classify intent
    classify_msg = CLASSIFY_PROMPT.format(question=user_query)
    response = await llm.ainvoke([
        SystemMessage(content="You are a query classifier."),
        HumanMessage(content=classify_msg)
    ])
    query_type = response.content.strip().lower().strip('"').strip("'")
    
    # Validate classification
    valid_types = {"data_query", "insight", "comparison", "trend", "general"}
    if query_type not in valid_types:
        query_type = "data_query"  # default to data query
    
    # Fetch schema for SQL-requiring queries
    schema_context = ""
    if query_type in ("data_query", "comparison", "trend"):
        schema_context = await get_database_schema(db)
    
    return {
        "query_type": query_type,
        "schema_context": schema_context,
        "retry_count": 0,
        "max_retries": 3
    }


async def generate_sql_node(state: AgentState, db, llm) -> dict:
    """Generate SQL from the user's natural language query."""
    user_query = state["user_query"]
    schema = state.get("schema_context", "")
    error = state.get("sql_error", "")
    
    # Build few-shot context
    few_shot = "\n\nEXAMPLES:\n"
    for ex in FEW_SHOT_EXAMPLES:
        few_shot += f"Q: {ex['question']}\nSQL: {ex['sql']}\n\n"
    
    prompt = SQL_GENERATION_PROMPT.format(
        schema=schema + few_shot,
        question=user_query,
        error=error or "None"
    )
    
    response = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])
    
    # Clean the SQL response
    sql = response.content.strip()
    # Remove markdown code fences if present
    if sql.startswith("```"):
        lines = sql.split('\n')
        sql = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
    sql = sql.strip().rstrip(';') + ';'
    
    return {
        "generated_sql": sql,
        "messages": [AIMessage(content=f"Generated SQL: {sql}")]
    }


async def validate_sql_node(state: AgentState, db, llm) -> dict:
    """Validate the generated SQL for safety and correctness."""
    sql = state.get("generated_sql", "")
    
    is_valid, error = validate_sql_tool(sql)
    
    if not is_valid:
        retry_count = state.get("retry_count", 0)
        return {
            "sql_valid": False,
            "sql_error": error,
            "retry_count": retry_count + 1
        }
    
    return {
        "sql_valid": True,
        "sql_error": None
    }


async def execute_query_node(state: AgentState, db, llm) -> dict:
    """Execute the validated SQL query against the database."""
    sql = state.get("generated_sql", "")
    
    try:
        results, columns = await execute_query_tool(db, sql)
        return {
            "query_results": results,
            "result_columns": columns,
            "error": None
        }
    except Exception as e:
        retry_count = state.get("retry_count", 0)
        return {
            "query_results": None,
            "result_columns": None,
            "error": str(e),
            "sql_error": str(e),
            "retry_count": retry_count + 1
        }


async def build_chart_node(state: AgentState, db, llm) -> dict:
    """Auto-select chart type and build Plotly visualization from results."""
    results = state.get("query_results", [])
    columns = state.get("result_columns", [])
    user_query = state.get("user_query", "")
    
    if not results:
        return {"chart_json": None, "chart_type": "none"}
    
    # Auto-select chart type
    chart_type = auto_select_chart(columns, results, len(results))
    
    # Build chart
    chart_json = build_chart_from_results(
        results, columns, chart_type, title=user_query[:80]
    )
    
    return {
        "chart_json": chart_json,
        "chart_type": chart_type
    }


async def generate_narrative_node(state: AgentState, db, llm) -> dict:
    """Generate a natural language narrative from query results."""
    results = state.get("query_results", [])
    sql = state.get("generated_sql", "")
    user_query = state.get("user_query", "")
    chart_type = state.get("chart_type", "none")
    
    if not results:
        return {"narrative": "No data found for your query. Try rephrasing or checking if the survey data has been loaded."}
    
    # Truncate results for prompt
    display_results = results[:20]  # limit context
    
    prompt = NARRATIVE_PROMPT.format(
        question=user_query,
        sql=sql,
        results=json.dumps(display_results, indent=2, default=str),
        chart_type=chart_type
    )
    
    response = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])
    
    return {
        "narrative": response.content.strip()
    }


async def insight_node(state: AgentState, db, llm) -> dict:
    """Handle insight-type queries using pre-computed NLP results."""
    user_query = state.get("user_query", "")
    survey_id = state.get("survey_id")
    
    # Gather available NLP data
    sentiment = {}
    themes = []
    
    if survey_id:
        try:
            sentiment = await get_sentiment_summary(db, survey_id)
        except Exception:
            pass
        try:
            themes = await get_themes_summary(db, survey_id)
        except Exception:
            pass
    
    # Build context for LLM
    context = f"""
SENTIMENT SUMMARY: {json.dumps(sentiment, default=str)}
EXTRACTED THEMES: {json.dumps(themes, default=str)}

User Question: {user_query}

Provide a detailed, insightful answer based on the NLP analysis data above.
If sentiment or theme data is empty, suggest running the NLP analysis first.
"""
    
    response = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=context)
    ])
    
    # Build a simple sentiment chart if data available
    chart_json = None
    if sentiment and sentiment.get("total", 0) > 0:
        import pandas as pd
        sent_df = pd.DataFrame([
            {"Sentiment": "Positive", "Count": sentiment.get("positive", 0)},
            {"Sentiment": "Neutral", "Count": sentiment.get("neutral", 0)},
            {"Sentiment": "Negative", "Count": sentiment.get("negative", 0)},
        ])
        from app.services.chart_builder import build_donut_chart
        chart_json = build_donut_chart(sent_df, labels="Sentiment", values="Count", title="Sentiment Distribution")
    
    return {
        "narrative": response.content.strip(),
        "chart_json": chart_json,
        "chart_type": "donut" if chart_json else "none",
        "query_results": [sentiment] if sentiment else [],
        "result_columns": list(sentiment.keys()) if sentiment else []
    }


async def respond_node(state: AgentState, db, llm) -> dict:
    """Combine chart and narrative into final response."""
    narrative = state.get("narrative", "")
    chart_json = state.get("chart_json")
    chart_type = state.get("chart_type", "none")
    query_results = state.get("query_results", [])
    generated_sql = state.get("generated_sql")
    error = state.get("error")
    
    final_response = {
        "narrative": narrative,
        "chart": chart_json,
        "chart_type": chart_type,
        "data": query_results[:50] if query_results else [],  # Cap data rows
        "sql": generated_sql,
        "error": error
    }
    
    return {
        "final_response": final_response,
        "messages": [AIMessage(content=narrative)]
    }


async def error_node(state: AgentState, db, llm) -> dict:
    """Handle unrecoverable errors gracefully."""
    error = state.get("error") or state.get("sql_error") or "Unknown error"
    
    return {
        "final_response": {
            "narrative": f"I encountered an issue processing your query: {error}. "
                        f"Could you try rephrasing your question?",
            "chart": None,
            "chart_type": "none",
            "data": [],
            "sql": state.get("generated_sql"),
            "error": error
        },
        "messages": [AIMessage(content=f"Error: {error}")]
    }


async def general_node(state: AgentState, db, llm) -> dict:
    """Handle general questions that don't require SQL or NLP lookups."""
    user_query = state.get("user_query", "")
    
    response = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_query)
    ])
    
    return {
        "narrative": response.content.strip(),
        "chart_json": None,
        "chart_type": "none",
        "final_response": {
            "narrative": response.content.strip(),
            "chart": None,
            "chart_type": "none",
            "data": [],
            "sql": None,
            "error": None
        },
        "messages": [AIMessage(content=response.content.strip())]
    }
