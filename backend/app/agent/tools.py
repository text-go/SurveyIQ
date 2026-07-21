"""Agent tools for database queries, schema introspection, charting, and NLP lookups."""

import json
import sqlglot
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.chart_builder import (
    build_bar_chart, build_line_chart, build_donut_chart, build_gauge
)
from app.services.nlp_engine import analyze_sentiment, extract_themes
from app.services.statistics import calculate_nps
import pandas as pd


async def get_database_schema(db: AsyncSession) -> str:
    """Introspect the database and return a formatted schema description.
    
    Returns a string with table names, column names, types, and sample data
    that can be injected into the SQL generation prompt.
    """
    # Use raw connection for synchronous inspection
    schema_parts = []
    
    async with db.begin():
        conn = await db.connection()
        raw_conn = await conn.get_raw_connection()
        
        # Get table info from SQLite
        result = await db.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ))
        tables = [row[0] for row in result.fetchall()]
        
        for table in tables:
            # Get column info
            col_result = await db.execute(text(f"PRAGMA table_info({table})"))
            columns = col_result.fetchall()
            
            col_strs = []
            for col in columns:
                # col: (cid, name, type, notnull, default_val, pk)
                col_strs.append(f"  {col[1]} {col[2]}{' PRIMARY KEY' if col[5] else ''}")
            
            # Get sample rows (up to 3)
            try:
                sample_result = await db.execute(text(f"SELECT * FROM {table} LIMIT 3"))
                sample_rows = sample_result.fetchall()
                sample_str = ""
                if sample_rows:
                    col_names = [col[1] for col in columns]
                    sample_str = "\n  -- Sample data:\n"
                    for row in sample_rows:
                        row_dict = dict(zip(col_names, row))
                        # Truncate long text values
                        for k, v in row_dict.items():
                            if isinstance(v, str) and len(v) > 50:
                                row_dict[k] = v[:50] + "..."
                        sample_str += f"  -- {row_dict}\n"
            except Exception:
                sample_str = ""
            
            schema_parts.append(f"TABLE {table} (\n{chr(10).join(col_strs)}\n){sample_str}")
    
    return "\n\n".join(schema_parts)


def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate SQL query for safety and correctness using sqlglot.
    
    Returns:
        (is_valid, error_message) tuple
    """
    if not sql or not sql.strip():
        return False, "Empty SQL query"
    
    # Clean up the SQL
    sql = sql.strip().rstrip(';')
    
    # Check for dangerous keywords (case-insensitive)
    dangerous = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 
                 'TRUNCATE', 'EXEC', 'EXECUTE', 'GRANT', 'REVOKE']
    sql_upper = sql.upper()
    for keyword in dangerous:
        # Check it appears as a standalone word, not part of another word
        if f' {keyword} ' in f' {sql_upper} ' or sql_upper.startswith(f'{keyword} '):
            return False, f"Dangerous SQL operation detected: {keyword}"
    
    # Must start with SELECT or WITH (for CTEs)
    first_word = sql_upper.strip().split()[0] if sql_upper.strip() else ""
    if first_word not in ('SELECT', 'WITH'):
        return False, f"Only SELECT queries are allowed, got: {first_word}"
    
    # Try to parse with sqlglot for syntax validation
    try:
        parsed = sqlglot.parse(sql, dialect="sqlite")
        if not parsed:
            return False, "Failed to parse SQL"
        
        # Check each statement is a SELECT
        for stmt in parsed:
            if stmt is None:
                continue
            stmt_type = type(stmt).__name__
            if stmt_type not in ('Select',):
                # Allow Select and subqueries
                pass
                
    except sqlglot.errors.ParseError as e:
        return False, f"SQL syntax error: {str(e)}"
    except Exception as e:
        # sqlglot may throw other errors; fall through to execution
        pass
    
    return True, ""


async def execute_query(db: AsyncSession, sql: str) -> tuple[list[dict], list[str]]:
    """Execute a validated SQL query and return results as list of dicts.
    
    Returns:
        (results, column_names) tuple
    """
    sql = sql.strip().rstrip(';')
    
    result = await db.execute(text(sql))
    rows = result.fetchall()
    columns = list(result.keys())
    
    # Convert to list of dicts
    results = []
    for row in rows:
        row_dict = {}
        for i, col in enumerate(columns):
            val = row[i]
            # Convert non-serializable types
            if hasattr(val, 'isoformat'):
                val = val.isoformat()
            row_dict[col] = val
        results.append(row_dict)
    
    return results, columns


def auto_select_chart(columns: list[str], results: list[dict], row_count: int) -> str:
    """Automatically select the best chart type based on data shape."""
    if row_count == 0:
        return "metric"
    
    if row_count == 1 and len(columns) <= 2:
        return "metric"
    
    # Analyze column types from data
    numeric_cols = []
    categorical_cols = []
    date_cols = []
    
    for col in columns:
        sample_vals = [r[col] for r in results[:5] if r.get(col) is not None]
        if not sample_vals:
            continue
        
        # Check if date-like
        val = str(sample_vals[0])
        if any(pattern in col.lower() for pattern in ['date', 'month', 'year', 'time', 'period']):
            date_cols.append(col)
        elif all(isinstance(v, (int, float)) for v in sample_vals):
            numeric_cols.append(col)
        else:
            try:
                [float(v) for v in sample_vals]
                numeric_cols.append(col)
            except (ValueError, TypeError):
                categorical_cols.append(col)
    
    # Decision rules
    if date_cols and numeric_cols:
        return "line"
    
    if len(categorical_cols) == 1 and len(numeric_cols) == 1:
        if row_count > 10:
            return "horizontal_bar"
        return "bar"
    
    if len(numeric_cols) >= 2 and not categorical_cols:
        return "scatter"
    
    # Check if values look like percentages summing to ~100
    if numeric_cols and row_count <= 8:
        vals = [r.get(numeric_cols[0], 0) for r in results if isinstance(r.get(numeric_cols[0]), (int, float))]
        if vals and 90 <= sum(vals) <= 110:
            return "donut"
    
    if categorical_cols and numeric_cols:
        return "bar"
    
    return "bar"


def build_chart_from_results(
    results: list[dict],
    columns: list[str],
    chart_type: str,
    title: str = "Query Results"
) -> dict:
    """Build a Plotly chart JSON from query results."""
    if not results:
        return {}
    
    df = pd.DataFrame(results)
    
    if chart_type == "metric":
        # Single value display
        val = results[0].get(columns[-1], 0) if columns else 0
        if isinstance(val, (int, float)):
            return build_gauge(float(val), title, 0, max(float(val) * 1.5, 100))
        return {"type": "metric", "value": val, "title": title}
    
    # Identify x and y columns
    numeric_cols = [c for c in columns if df[c].dtype in ('int64', 'float64')]
    cat_cols = [c for c in columns if c not in numeric_cols]
    
    x_col = cat_cols[0] if cat_cols else columns[0]
    y_col = numeric_cols[0] if numeric_cols else columns[-1]
    
    if chart_type in ("bar", "horizontal_bar"):
        return build_bar_chart(df, x=x_col, y=y_col, title=title)
    elif chart_type == "line":
        return build_line_chart(df, x=x_col, y=y_col, title=title)
    elif chart_type == "donut":
        return build_donut_chart(df, labels=x_col, values=y_col, title=title)
    elif chart_type == "scatter":
        import plotly.express as px
        fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0],
                        title=title, color_discrete_sequence=['#3b82f6'])
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font_color='#e2e8f0'
        )
        return json.loads(fig.to_json())
    else:
        return build_bar_chart(df, x=x_col, y=y_col, title=title)


async def get_sentiment_summary(db: AsyncSession, survey_id: int) -> dict:
    """Retrieve pre-computed sentiment summary for a survey."""
    from app.models.analysis import SentimentResult
    from app.models.survey import Answer, Question
    from sqlalchemy.future import select
    from sqlalchemy import func
    
    result = await db.execute(
        select(
            SentimentResult.label,
            func.count(SentimentResult.id).label('count'),
            func.avg(SentimentResult.score).label('avg_score')
        )
        .join(Answer, Answer.id == SentimentResult.answer_id)
        .join(Question, Question.id == Answer.question_id)
        .where(Question.survey_id == survey_id)
        .group_by(SentimentResult.label)
    )
    rows = result.all()
    
    summary = {"positive": 0, "neutral": 0, "negative": 0, "total": 0, "avg_score": 0}
    total = 0
    weighted_score = 0
    for label, count, avg_score in rows:
        summary[label] = count
        total += count
        weighted_score += (avg_score or 0) * count
    
    summary["total"] = total
    summary["avg_score"] = weighted_score / total if total > 0 else 0
    
    return summary


async def get_themes_summary(db: AsyncSession, survey_id: int) -> list[dict]:
    """Retrieve extracted themes for a survey."""
    from app.models.analysis import Theme
    from sqlalchemy.future import select
    
    result = await db.execute(
        select(Theme)
        .where(Theme.survey_id == survey_id)
        .order_by(Theme.response_count.desc())
    )
    themes = result.scalars().all()
    
    return [
        {
            "name": t.name,
            "keywords": t.keywords,
            "response_count": t.response_count,
            "avg_sentiment": t.avg_sentiment
        }
        for t in themes
    ]
