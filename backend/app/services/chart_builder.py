import plotly.graph_objects as go
import plotly.express as px
import json

DARK_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font_color='#e2e8f0',
    title_font_color='#f8fafc',
    legend_font_color='#cbd5e1'
)
COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#f43f5e', '#8b5cf6', '#06b6d4', '#ec4899']

def build_bar_chart(data, x, y, title):
    fig = px.bar(data, x=x, y=y, title=title, color_discrete_sequence=COLORS)
    fig.update_layout(**DARK_LAYOUT)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor='rgba(255,255,255,0.1)')
    return json.loads(fig.to_json())

def build_line_chart(data, x, y, title):
    fig = px.line(data, x=x, y=y, title=title, color_discrete_sequence=COLORS)
    fig.update_layout(**DARK_LAYOUT)
    fig.update_xaxes(gridcolor='rgba(255,255,255,0.1)')
    fig.update_yaxes(gridcolor='rgba(255,255,255,0.1)')
    return json.loads(fig.to_json())

def build_pie_chart(data, labels, values, title):
    fig = px.pie(data, names=labels, values=values, title=title, color_discrete_sequence=COLORS)
    fig.update_layout(**DARK_LAYOUT)
    return json.loads(fig.to_json())

def build_donut_chart(data, labels, values, title):
    fig = px.pie(data, names=labels, values=values, title=title, hole=0.5, color_discrete_sequence=COLORS)
    fig.update_layout(**DARK_LAYOUT)
    return json.loads(fig.to_json())

def build_heatmap(data, x, y, z, title):
    fig = go.Figure(data=go.Heatmap(z=data[z], x=data[x], y=data[y], colorscale='Viridis'))
    fig.update_layout(title=title, **DARK_LAYOUT)
    return json.loads(fig.to_json())

def build_gauge(value, title, min_val, max_val):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': title},
        gauge={'axis': {'range': [min_val, max_val]},
               'bar': {'color': COLORS[0]}}
    ))
    fig.update_layout(**DARK_LAYOUT)
    return json.loads(fig.to_json())
