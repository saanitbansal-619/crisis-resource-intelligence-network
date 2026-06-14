"""
Humanitarian Resource Coordination Dashboard — Crisis Resource Intelligence Network.

Consumes the FastAPI backend and presents crisis monitoring, resource gaps,
and supply-demand intelligence for NGO and field coordination workflows.

Run: streamlit run dashboard/app.py
"""

import html
import json
from datetime import datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(
    page_title="Crisis Resource Intelligence Network",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DEFAULT_API_BASE = "http://127.0.0.1:8001"

# Humanitarian operations color palette
COLOR_BG = "#F6F7F9"
COLOR_CARD = "#FFFFFF"
COLOR_TEXT = "#1F2933"
COLOR_SECONDARY = "#475467"
COLOR_MUTED = "#667085"
COLOR_PRIMARY = "#1F4E79"
COLOR_CRITICAL = "#B42318"
COLOR_SEVERE = "#B54708"
COLOR_SURPLUS = "#027A48"
COLOR_BORDER = "#E5E7EB"
COLOR_STABLE = "#94A3B8"

STATUS_DISPLAY = {
    "critical shortage": "Critical Need",
    "severe shortage": "Severe Need",
    "moderate shortage": "Moderate Need",
    "surplus": "Available Surplus",
    "stable": "Stable",
}

# Single source of truth for map marker colors and custom legend
STATUS_COLOR_MAP = {
    "Critical Need": COLOR_CRITICAL,
    "Severe Need": COLOR_SEVERE,
    "Moderate Need": COLOR_SECONDARY,
    "Available Surplus": COLOR_SURPLUS,
    "Stable": COLOR_STABLE,
}

MAP_LEGEND_ORDER = [
    "Critical Need",
    "Severe Need",
    "Moderate Need",
    "Available Surplus",
]

RESOURCE_LABELS = {
    "food_kits": "Food Kits",
    "water_kits": "Water Kits",
    "insulin": "Insulin",
    "antibiotics": "Antibiotics",
    "shelter_tents": "Shelter Tents",
    "blankets": "Blankets",
    "hygiene_kits": "Hygiene Kits",
    "medical_staff": "Medical Staff",
    "volunteers": "Volunteers",
}

COLUMN_LABELS = {
    "zone_name": "Zone",
    "country": "Country",
    "admin_region": "Region",
    "resource_type": "Resource",
    "total_available": "Available",
    "total_needed": "Needed",
    "shortage_gap": "Gap",
    "shortage_ratio": "Shortage Ratio",
    "urgency_level": "Urgency",
    "mismatch_score": "Priority Score",
    "status_label": "Status",
    "total_shortage_gap": "Net Gap",
    "number_of_zones": "Zones",
    "critical_shortage_count": "Critical",
    "severe_shortage_count": "Severe",
    "surplus_count": "Surplus",
}

CHART_TEMPLATE = "plotly_white"
CHART_BG = COLOR_CARD
CHART_PAPER = COLOR_BG

API_BASE_URL = DEFAULT_API_BASE


def format_resource_name(value) -> str:
    """Return a stakeholder-friendly resource type label."""
    if not value or pd.isna(value):
        return ""
    return RESOURCE_LABELS.get(value, str(value).replace("_", " ").title())


def format_resource_label(resource_type: str) -> str:
    return format_resource_name(resource_type)


def format_status_label(status: str) -> str:
    """Map raw database status values to stakeholder-facing display labels."""
    if not status or pd.isna(status):
        return ""
    normalized = str(status).strip().lower()
    return STATUS_DISPLAY.get(normalized, str(status).replace("_", " ").title())


def rename_display_columns(df: pd.DataFrame, extra_labels: dict | None = None) -> pd.DataFrame:
    labels = {**COLUMN_LABELS, **(extra_labels or {})}
    return df.rename(columns={k: v for k, v in labels.items() if k in df.columns})


def prepare_display_df(
    df: pd.DataFrame,
    format_resources: bool = True,
    format_statuses: bool = True,
    extra_labels: dict | None = None,
) -> pd.DataFrame:
    display_df = df.copy()
    if format_resources and "resource_type" in display_df.columns:
        display_df["resource_type"] = display_df["resource_type"].apply(format_resource_label)
    if format_statuses and "status_label" in display_df.columns:
        display_df["status_label"] = display_df["status_label"].apply(format_status_label)
    return rename_display_columns(display_df, extra_labels=extra_labels)


def build_zone_resource_label(zone_name: str, resource_type: str) -> str:
    return f"{zone_name} / {format_resource_label(resource_type)}"


def inject_styles() -> None:
    """Apply website-style humanitarian dashboard styling."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}

        /* Hide sidebar completely */
        section[data-testid="stSidebar"],
        [data-testid="stSidebar"],
        [data-testid="collapsedControl"],
        [data-testid="stSidebarNav"] {{
            display: none !important;
        }}

        .stApp {{
            background-color: {COLOR_BG};
            color: {COLOR_TEXT};
        }}

        header[data-testid="stHeader"] {{
            background: transparent;
        }}

        .block-container {{
            max-width: 1500px !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            padding-top: 1.5rem !important;
            padding-bottom: 2.5rem !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }}
        section[data-testid="stMain"] > div {{
            max-width: 1500px !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }}

        /* Typography & contrast */
        h1, h2, h3, h4, p, li, label, span {{
            color: {COLOR_TEXT};
        }}

        .stMarkdown, .stText {{
            color: {COLOR_TEXT} !important;
        }}

        label, .stSelectbox label, .stTextInput label {{
            color: {COLOR_SECONDARY} !important;
            font-weight: 500 !important;
            font-size: 0.85rem !important;
        }}

        /* Info cards */
        .info-card {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 1rem 1.15rem;
            margin: 0.65rem 0 0.85rem 0;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
        }}
        .info-card-title {{
            font-size: 1rem;
            font-weight: 700;
            color: {COLOR_TEXT};
            margin-bottom: 0.55rem;
        }}
        .info-card-body {{
            font-size: 0.93rem;
            color: {COLOR_SECONDARY};
            line-height: 1.6;
            margin: 0;
        }}
        .info-card-body ul {{
            margin: 0.4rem 0 0 1.1rem;
            padding: 0;
        }}
        .info-card-body li {{
            margin-bottom: 0.35rem;
            color: {COLOR_SECONDARY};
        }}
        .transparency-note {{
            font-size: 0.88rem;
            color: {COLOR_MUTED};
            line-height: 1.55;
            margin-top: 0.75rem;
            padding-top: 0.75rem;
            border-top: 1px solid {COLOR_BORDER};
        }}
        .steps-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.75rem;
            margin: 0.5rem 0 0.85rem 0;
        }}
        @media (max-width: 900px) {{
            .steps-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        @media (max-width: 600px) {{
            .steps-grid {{ grid-template-columns: 1fr; }}
        }}
        .step-card {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 0.85rem 0.95rem;
            min-height: 110px;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
        }}
        .step-num {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.55rem;
            height: 1.55rem;
            border-radius: 50%;
            background: {COLOR_PRIMARY};
            color: white;
            font-size: 0.78rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }}
        .step-text {{
            font-size: 0.88rem;
            color: {COLOR_SECONDARY};
            line-height: 1.5;
            margin: 0;
        }}
        .pipeline-flow {{
            margin-top: 0.75rem;
            padding: 0.75rem 0.9rem;
            background: #F9FAFB;
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            font-size: 0.86rem;
            font-weight: 500;
            color: {COLOR_PRIMARY};
            text-align: center;
            line-height: 1.5;
        }}
        .sources-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-top: 0.5rem;
        }}
        @media (max-width: 700px) {{
            .sources-grid {{ grid-template-columns: 1fr; }}
        }}
        .source-column-title {{
            font-size: 0.82rem;
            font-weight: 700;
            color: {COLOR_PRIMARY};
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.45rem;
        }}

        /* Hero header */
        .hero-card {{
            width: 100%;
            box-sizing: border-box;
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 12px;
            padding: 1.35rem 1.5rem 1.2rem;
            margin-bottom: 0.85rem;
            box-shadow: 0 2px 8px rgba(16, 24, 40, 0.06);
        }}
        .hero-eyebrow {{
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: {COLOR_PRIMARY};
            margin-bottom: 0.45rem;
        }}
        .hero-title {{
            font-size: 1.85rem;
            font-weight: 700;
            color: {COLOR_TEXT};
            line-height: 1.2;
            margin: 0 0 0.4rem 0;
        }}
        .hero-subtitle {{
            font-size: 1rem;
            color: {COLOR_SECONDARY};
            line-height: 1.5;
            margin: 0;
            max-width: 720px;
        }}

        /* Website-style tab navigation */
        div[data-testid="stTabs"] {{
            width: 100%;
            box-sizing: border-box;
            margin-top: 0.25rem;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
            gap: 0;
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px 10px 0 0;
            padding: 0.35rem 0.5rem 0;
            border-bottom: 1px solid {COLOR_BORDER};
        }}
        div[data-testid="stTabs"] [data-baseweb="tab"] {{
            height: 42px;
            padding: 0 16px;
            color: {COLOR_SECONDARY} !important;
            font-weight: 500;
            font-size: 0.88rem;
            background: transparent !important;
            border: none !important;
            border-radius: 6px 6px 0 0 !important;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab"]:hover {{
            color: {COLOR_PRIMARY} !important;
            background: #F2F4F7 !important;
        }}
        div[data-testid="stTabs"] [aria-selected="true"] {{
            color: {COLOR_PRIMARY} !important;
            font-weight: 600 !important;
            background: {COLOR_BG} !important;
            border-bottom: 2px solid {COLOR_PRIMARY} !important;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab-panel"] {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-top: none;
            border-radius: 0 0 10px 10px;
            padding: 1.1rem 1.15rem 1.25rem;
            box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04);
        }}

        .section-header {{
            font-size: 1.1rem;
            font-weight: 700;
            color: {COLOR_TEXT};
            margin: 0 0 0.65rem 0;
            padding-bottom: 0.4rem;
            border-bottom: 1px solid {COLOR_BORDER};
        }}
        .subsection-header {{
            font-size: 0.95rem;
            font-weight: 600;
            color: {COLOR_TEXT};
            margin: 1rem 0 0.55rem 0;
        }}
        .ops-note {{
            background-color: #F9FAFB;
            border: 1px solid {COLOR_BORDER};
            border-left: 3px solid {COLOR_PRIMARY};
            padding: 0.75rem 1rem;
            border-radius: 8px;
            color: {COLOR_SECONDARY};
            font-size: 0.92rem;
            margin: 0.35rem 0 0.85rem 0;
            line-height: 1.55;
        }}

        .metric-card {{
            background-color: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 0.75rem 0.95rem;
            min-height: 78px;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
        }}
        .metric-label {{
            font-size: 0.74rem;
            font-weight: 500;
            color: {COLOR_SECONDARY};
            margin-bottom: 0.35rem;
            line-height: 1.3;
        }}
        .metric-value {{
            font-size: 1.45rem;
            font-weight: 700;
            color: {COLOR_TEXT};
            line-height: 1.15;
        }}
        .metric-accent-primary {{ border-top: 3px solid {COLOR_PRIMARY}; }}
        .metric-accent-neutral {{ border-top: 3px solid {COLOR_STABLE}; }}
        .metric-accent-critical {{ border-top: 3px solid {COLOR_CRITICAL}; }}
        .metric-accent-severe {{ border-top: 3px solid {COLOR_SEVERE}; }}
        .metric-accent-surplus {{ border-top: 3px solid {COLOR_SURPLUS}; }}

        .content-card {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 0.85rem;
            margin: 0.65rem 0;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.04);
        }}

        div[data-testid="stDataFrame"] {{
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            overflow: hidden;
        }}

        .stButton > button {{
            background-color: {COLOR_PRIMARY};
            color: #FFFFFF !important;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            padding: 0.45rem 1rem;
        }}
        .stButton > button:hover,
        .stButton > button:focus,
        .stButton > button:active {{
            background-color: #163d5e;
            color: #FFFFFF !important;
            border: none;
        }}
        .stButton > button * {{
            color: #FFFFFF !important;
        }}
        .stDownloadButton {{
            margin: 0 !important;
            padding: 0 !important;
        }}
        .stDownloadButton > button {{
            width: 100% !important;
            height: 44px !important;
            min-height: 44px !important;
            padding: 0 1rem !important;
            margin: 0 !important;
            background-color: #1F4E79 !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-size: 0.95rem !important;
            font-weight: 500 !important;
            font-family: inherit !important;
            line-height: 1 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-sizing: border-box !important;
        }}
        .stDownloadButton > button * {{
            color: #FFFFFF !important;
            font-size: 0.95rem !important;
            font-weight: 500 !important;
            font-family: inherit !important;
            line-height: 1 !important;
        }}
        .stDownloadButton > button:hover,
        .stDownloadButton > button:focus,
        .stDownloadButton > button:active {{
            background-color: #17436B !important;
            color: #FFFFFF !important;
        }}
        [data-testid="stHtml"] {{
            margin: 0 !important;
            padding: 0 !important;
            height: 46px !important;
            min-height: 46px !important;
        }}
        [data-testid="stHtml"] iframe {{
            height: 46px !important;
            min-height: 46px !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            display: block !important;
        }}
        .brief-action-status {{
            text-align: center;
            color: #027A48;
            font-size: 0.9rem;
            font-weight: 600;
            margin-top: 8px;
            min-height: 1.1rem;
        }}
        div[data-testid="column"]:has(.zone-brief-actions-primary) button,
        div[data-testid="column"]:has(.zone-brief-actions-secondary) button,
        div[data-testid="column"]:has(.zone-brief-actions-secondary) a {{
            background-color: {COLOR_PRIMARY} !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            padding: 0.6rem 1.25rem !important;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.08);
            text-decoration: none !important;
        }}
        div[data-testid="column"]:has(.zone-brief-actions-primary) button:hover,
        div[data-testid="column"]:has(.zone-brief-actions-primary) button:focus,
        div[data-testid="column"]:has(.zone-brief-actions-primary) button:active,
        div[data-testid="column"]:has(.zone-brief-actions-secondary) button:hover,
        div[data-testid="column"]:has(.zone-brief-actions-secondary) button:focus,
        div[data-testid="column"]:has(.zone-brief-actions-secondary) button:active,
        div[data-testid="column"]:has(.zone-brief-actions-secondary) a:hover,
        div[data-testid="column"]:has(.zone-brief-actions-secondary) a:focus,
        div[data-testid="column"]:has(.zone-brief-actions-secondary) a:active {{
            background-color: #163d5e !important;
            color: #FFFFFF !important;
            border: none !important;
        }}
        div[data-testid="column"]:has(.zone-brief-actions-primary) button *,
        div[data-testid="column"]:has(.zone-brief-actions-secondary) button *,
        div[data-testid="column"]:has(.zone-brief-actions-secondary) a * {{
            color: #FFFFFF !important;
        }}
        .zone-brief-action-spacer {{
            margin-top: 0.35rem;
        }}

        .stTextInput input {{
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            color: {COLOR_TEXT};
            background: {COLOR_CARD};
        }}

        div[data-testid="stAlert"] {{
            border-radius: 8px;
        }}

        .map-legend-bar {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.75rem 1.5rem;
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px 10px 0 0;
            padding: 0.7rem 1rem;
            margin-top: 0.5rem;
        }}
        .map-legend-item {{
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            font-size: 0.86rem;
            font-weight: 500;
            color: {COLOR_TEXT};
        }}
        .map-legend-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
            flex-shrink: 0;
        }}
        div[data-testid="stPlotlyChart"] {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-top: none;
            border-radius: 0 0 10px 10px;
            padding: 0.35rem 0.5rem 0.65rem;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.04);
        }}
        .zone-details-card {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 1.1rem 1.25rem;
            margin: 1rem 0 0.85rem 0;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
        }}
        .zone-details-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: {COLOR_TEXT};
            margin-bottom: 0.85rem;
        }}
        .zone-details-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.65rem 1.25rem;
        }}
        @media (max-width: 768px) {{
            .zone-details-grid {{ grid-template-columns: 1fr; }}
        }}
        .zone-detail-item {{
            font-size: 0.9rem;
            line-height: 1.5;
        }}
        .zone-detail-label {{
            display: block;
            font-size: 0.78rem;
            font-weight: 600;
            color: {COLOR_MUTED};
            text-transform: uppercase;
            letter-spacing: 0.03em;
            margin-bottom: 0.15rem;
        }}
        .zone-detail-value {{
            color: {COLOR_TEXT};
            font-weight: 500;
        }}
        .zone-brief-card {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 1.2rem 1.3rem;
            margin: 0.85rem 0 0.65rem 0;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
        }}
        .zone-brief-title {{
            font-size: 1.1rem;
            font-weight: 700;
            color: {COLOR_TEXT};
            margin-bottom: 1rem;
            padding-bottom: 0.65rem;
            border-bottom: 1px solid {COLOR_BORDER};
        }}
        .zone-brief-section {{
            margin-bottom: 1.1rem;
        }}
        .zone-brief-section-title {{
            font-size: 0.95rem;
            font-weight: 700;
            color: {COLOR_PRIMARY};
            margin-bottom: 0.45rem;
        }}
        .zone-brief-paragraph {{
            font-size: 0.92rem;
            color: {COLOR_SECONDARY};
            line-height: 1.65;
            margin: 0 0 0.4rem 0;
        }}
        .zone-brief-list {{
            margin: 0.2rem 0 0.35rem 1.15rem;
            padding: 0;
            color: {COLOR_SECONDARY};
            font-size: 0.92rem;
            line-height: 1.6;
        }}
        .zone-brief-list li {{
            margin-bottom: 0.35rem;
        }}
        .zone-brief-transparency {{
            font-size: 0.86rem;
            color: {COLOR_MUTED};
            line-height: 1.55;
            margin-top: 0.5rem;
            padding-top: 0.75rem;
            border-top: 1px solid {COLOR_BORDER};
        }}
        .rag-context-card {{
            margin-top: 0.75rem;
        }}
        .rag-context-heading-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            margin-bottom: 0.85rem;
            padding-bottom: 0.65rem;
            border-bottom: 1px solid {COLOR_BORDER};
        }}
        .rag-context-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: {COLOR_TEXT};
        }}
        .rag-context-badge {{
            display: inline-block;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            color: {COLOR_PRIMARY};
            background: #E8F1FA;
            border: 1px solid #C7DDF2;
            border-radius: 999px;
            padding: 0.2rem 0.55rem;
            white-space: nowrap;
        }}
        .rag-summary-card {{
            background: #F8FAFC;
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.9rem;
        }}
        .rag-summary-text {{
            font-size: 0.92rem;
            color: {COLOR_SECONDARY};
            line-height: 1.65;
            margin: 0;
        }}
        .rag-source-card {{
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            padding: 0.85rem 0.95rem;
            margin-bottom: 0.75rem;
            background: {COLOR_CARD};
        }}
        .rag-source-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-bottom: 0.45rem;
        }}
        .rag-label {{
            display: inline-block;
            font-size: 0.72rem;
            font-weight: 600;
            border-radius: 999px;
            padding: 0.18rem 0.5rem;
        }}
        .rag-label-country {{
            color: #027A48;
            background: #ECFDF3;
            border: 1px solid #ABEFC6;
        }}
        .rag-label-fallback {{
            color: #B54708;
            background: #FFF6ED;
            border: 1px solid #F9DBAF;
        }}
        .rag-fallback-note {{
            font-size: 0.8rem;
            color: {COLOR_MUTED};
            line-height: 1.45;
            margin: 0.35rem 0 0.45rem 0;
            font-style: italic;
        }}
        .rag-summary-card .rag-context-badge {{
            margin-bottom: 0.55rem;
        }}
        .rag-summary-card .rag-context-transparency {{
            margin-top: 0.75rem;
            padding-top: 0.65rem;
            border-top: 1px solid {COLOR_BORDER};
        }}
        .rag-expander-wrap {{
            margin-top: -0.35rem;
            margin-bottom: 0.75rem;
        }}
        .rag-score {{
            font-size: 0.78rem;
            color: {COLOR_MUTED};
            font-weight: 500;
        }}
        .rag-source-title {{
            font-size: 0.94rem;
            font-weight: 600;
            color: {COLOR_TEXT};
            line-height: 1.45;
            margin-bottom: 0.35rem;
        }}
        .rag-source-meta {{
            font-size: 0.82rem;
            color: {COLOR_MUTED};
            margin-bottom: 0.45rem;
        }}
        .rag-source-preview {{
            font-size: 0.9rem;
            color: {COLOR_SECONDARY};
            line-height: 1.6;
            margin: 0 0 0.5rem 0;
        }}
        .rag-source-link {{
            font-size: 0.84rem;
            font-weight: 600;
            color: {COLOR_PRIMARY};
            text-decoration: none;
        }}
        .rag-source-link:hover {{
            text-decoration: underline;
        }}
        .rag-context-warning {{
            font-size: 0.9rem;
            color: #B54708;
            line-height: 1.55;
            margin: 0;
        }}
        .rag-context-empty {{
            font-size: 0.92rem;
            color: {COLOR_SECONDARY};
            line-height: 1.55;
            margin: 0;
        }}
        .rag-context-transparency {{
            font-size: 0.86rem;
            color: {COLOR_MUTED};
            line-height: 1.55;
            margin-top: 0.75rem;
            padding-top: 0.75rem;
            border-top: 1px solid {COLOR_BORDER};
        }}
        .ai-brief-card {{
            margin-top: 0.75rem;
        }}
        .ai-brief-draft-card {{
            margin-top: 0.75rem;
        }}
        .ai-brief-draft-label {{
            font-size: 0.95rem;
            font-weight: 700;
            color: {COLOR_PRIMARY};
            margin-bottom: 0.35rem;
        }}
        .ai-brief-note {{
            font-size: 0.92rem;
            color: {COLOR_SECONDARY};
            line-height: 1.6;
            margin: 0 0 0.85rem 0;
        }}
        .ai-brief-meta {{
            font-size: 0.78rem;
            color: {COLOR_MUTED};
            margin-bottom: 0.75rem;
        }}
        .ai-brief-output-wrap {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 1rem 1.1rem;
            margin-top: 0.75rem;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
        }}
        .ai-brief-output-wrap .ai-brief-transparency {{
            font-size: 0.86rem;
            color: {COLOR_MUTED};
            line-height: 1.55;
            margin: 0.85rem 0 0 0;
            padding-top: 0.75rem;
            border-top: 1px solid {COLOR_BORDER};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def fetch_json(endpoint: str, base_url: str, params: dict | None = None):
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def get_health(base_url: str) -> dict | None:
    return fetch_json("/health", base_url)


def get_overview(base_url: str) -> dict | None:
    return fetch_json("/reports/overview", base_url)


def get_critical_shortages(base_url: str, limit: int = 50) -> list | None:
    return fetch_json("/mismatches/critical", base_url, params={"limit": limit})


def get_surplus_resources(base_url: str, limit: int = 50) -> list | None:
    return fetch_json("/mismatches/surplus", base_url, params={"limit": limit})


def get_resource_summary(base_url: str) -> list | None:
    return fetch_json("/reports/resource-summary", base_url)


def get_mismatches(base_url: str, limit: int = 200) -> list | None:
    return fetch_json("/mismatches", base_url, params={"limit": limit})


def get_zones(base_url: str) -> list | None:
    return fetch_json("/resources/zones", base_url)


def get_zone_briefing(base_url: str, zone_id: str) -> dict | None:
    return fetch_json(f"/reports/zone-briefing/{zone_id}", base_url)


def get_rag_zone_context(base_url: str, zone_id: str) -> dict | None:
    return fetch_json(f"/reports/rag-zone-context/{zone_id}", base_url)


def get_ai_zone_briefing(base_url: str, zone_id: str) -> dict | None:
    """Fetch AI-assisted briefing (longer timeout for local Ollama generation)."""
    url = f"{base_url.rstrip('/')}/reports/ai-zone-briefing/{zone_id}"
    try:
        response = requests.get(url, timeout=200)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


RAG_UNAVAILABLE_MESSAGE = (
    "Retrieved crisis context is currently unavailable. "
    "Run the RAG corpus/chunk scripts and restart the API."
)
RAG_EMPTY_MESSAGE = "No retrieved crisis context available for this zone."
RAG_TRANSPARENCY_NOTE = (
    "This is retrieval-based context from ReliefWeb/GDACS records. "
    "It is not an LLM-generated analysis."
)
AI_BRIEF_UNAVAILABLE_MESSAGE = (
    "AI-assisted briefing is currently unavailable. "
    "Make sure Ollama is running and llama3.2 is available."
)
AI_BRIEF_NOTE = (
    "Optional local LLM draft generated from structured zone metrics and retrieved crisis context."
)
AI_BRIEF_REVIEW_NOTE = (
    "This is an AI-assisted draft and should be reviewed before operational use."
)


DATA_TRANSPARENCY_NOTE = (
    "Public crisis alert and humanitarian report data come from GDACS and ReliefWeb. "
    "Operational inventory and request data are simulated for prototype purposes because "
    "real NGO inventory data is generally not public."
)

RECOMMENDED_ACTIONS = [
    "Prioritize resources with the highest mismatch scores.",
    "Coordinate with partner organizations currently holding relevant inventory.",
    "Review Available Surplus zones for possible redistribution sources.",
    "Validate transportation access, security, and field capacity before moving supplies.",
    "Re-run ingestion/loading/mismatch scripts after new crisis or resource updates.",
]


def format_number(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, float) and value == int(value):
        return f"{int(value):,}"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return str(value)


def format_datetime(value) -> str:
    if not value:
        return "Not available"
    return str(value).replace("T", " ").split(".")[0]


def build_zone_dropdown_label(zone: dict) -> str:
    country = zone.get("country") or "Unknown country"
    return f"{zone.get('zone_id')} — {zone.get('zone_name')}, {country}"


def build_zone_operational_brief_sections(briefing: dict) -> list[dict]:
    """Build structured sections for the Zone Operational Brief."""
    zone = briefing.get("zone", {})
    priority_needs = briefing.get("priority_needs", [])
    inventory = briefing.get("inventory", [])
    requests = briefing.get("requests", [])
    alert = briefing.get("related_alert")

    zone_name = zone.get("zone_name", "Unknown Zone")
    country = zone.get("country") or "—"
    admin_region = zone.get("admin_region") or "—"
    population = format_number(zone.get("population_estimate"))

    overview_lines = [
        f"Zone: {zone_name}",
        f"Location: {country}, {admin_region}",
        f"Population estimate: {population}",
    ]

    if alert:
        alert_lines = [
            f"Title: {alert.get('title', '—')}",
            f"Event type: {alert.get('event_type', '—')}",
            f"Severity: {alert.get('severity_color', '—')}",
            f"Published: {format_datetime(alert.get('pub_date_parsed'))}",
            alert.get("description") or "No description available.",
            f"Source: {alert.get('link') or 'Not available'}",
        ]
    else:
        alert_lines = ["No directly linked GDACS alert was found for this zone."]

    if priority_needs:
        needs_lines = []
        for need in priority_needs:
            needs_lines.append(
                f"{format_resource_name(need.get('resource_type'))}: "
                f"{format_number(need.get('total_available'))} available, "
                f"{format_number(need.get('total_needed'))} needed, "
                f"gap {format_number(need.get('shortage_gap'))}, "
                f"urgency {need.get('urgency_level') or '—'}, "
                f"priority score {format_number(need.get('mismatch_score'))} "
                f"({format_status_label(need.get('status_label'))})"
            )
    else:
        needs_lines = ["No critical, severe, or moderate shortages are currently recorded."]

    if inventory:
        inventory_lines = []
        for item in inventory:
            inventory_lines.append(
                f"{format_resource_name(item.get('resource_type'))}: "
                f"{format_number(item.get('quantity_available'))} {item.get('unit') or 'units'} "
                f"({item.get('org_name', 'Unknown partner')}, {item.get('org_type') or 'partner'})"
            )
    else:
        inventory_lines = ["No inventory records are currently available for this zone."]

    if requests:
        request_lines = []
        for req in requests:
            request_lines.append(
                f"{format_resource_name(req.get('resource_type'))}: "
                f"{format_number(req.get('quantity_needed'))} needed, "
                f"urgency {req.get('urgency_level') or '—'}, "
                f"requested by {req.get('requested_by') or '—'}, "
                f"timestamp {format_datetime(req.get('request_timestamp'))}"
            )
    else:
        request_lines = ["No resource requests are currently recorded for this zone."]

    if priority_needs:
        resource_names = ", ".join(
            format_resource_name(need.get("resource_type")) for need in priority_needs
        )
        largest_gap_need = max(priority_needs, key=lambda need: need.get("shortage_gap") or 0)
        interpretation = (
            f"This zone shows priority needs across {resource_names}. "
            f"The largest shortage gap is {format_resource_name(largest_gap_need.get('resource_type'))} "
            f"with a gap of {format_number(largest_gap_need.get('shortage_gap'))}. "
            "Response planning should prioritize the highest-score resources first while "
            "validating partner capacity and field access."
        )
    else:
        interpretation = (
            "This zone does not currently show critical, severe, or moderate shortages. "
            "Continue routine monitoring and maintain coordination with partner organizations."
        )

    return [
        {"title": "Zone Overview", "lines": overview_lines, "bullets": False},
        {"title": "Related Disaster Alert", "lines": alert_lines, "bullets": False},
        {"title": "Priority Needs", "lines": needs_lines, "bullets": True},
        {"title": "Available Inventory", "lines": inventory_lines, "bullets": True},
        {"title": "Resource Requests", "lines": request_lines, "bullets": True},
        {"title": "Operational Interpretation", "lines": [interpretation], "bullets": False},
        {
            "title": "Recommended Immediate Actions",
            "lines": [f"{index}. {action}" for index, action in enumerate(RECOMMENDED_ACTIONS, start=1)],
            "bullets": False,
        },
        {"title": "Data Transparency Note", "lines": [DATA_TRANSPARENCY_NOTE], "bullets": False},
    ]


def generate_zone_operational_brief_text(
    briefing: dict,
    rag_context: dict | None = None,
) -> str:
    """Return plain-text Zone Operational Brief for copy/export."""
    zone = briefing.get("zone", {})
    zone_name = zone.get("zone_name", "Unknown Zone")
    lines = [f"Zone Operational Brief: {zone_name}", ""]
    for section in build_zone_operational_brief_sections(briefing):
        lines.append(section["title"])
        for item in section["lines"]:
            prefix = "- " if section["bullets"] else ""
            lines.append(f"{prefix}{item}")
        lines.append("")
    lines.extend(build_retrieved_crisis_context_text(rag_context))
    return "\n".join(lines).strip()


def generate_situation_report(briefing: dict) -> str:
    return generate_zone_operational_brief_text(briefing)


def generate_priority_needs_brief(briefing: dict) -> str:
    return generate_zone_operational_brief_text(briefing)


def generate_reallocation_recommendation(briefing: dict) -> str:
    return generate_zone_operational_brief_text(briefing)


def generate_disaster_context_summary(briefing: dict) -> str:
    return generate_zone_operational_brief_text(briefing)


def generate_zone_operational_brief_html(briefing: dict) -> str:
    """Return styled HTML for the in-app Zone Operational Brief preview."""
    parts = [
        '<div class="zone-brief-card">',
        '<div class="zone-brief-title">Zone Operational Brief</div>',
    ]
    for section in build_zone_operational_brief_sections(briefing):
        parts.append('<div class="zone-brief-section">')
        parts.append(
            f'<div class="zone-brief-section-title">{html.escape(section["title"])}</div>'
        )
        if section["bullets"]:
            parts.append('<ul class="zone-brief-list">')
            for line in section["lines"]:
                parts.append(f"<li>{html.escape(line)}</li>")
            parts.append("</ul>")
        else:
            for line in section["lines"]:
                css_class = (
                    "zone-brief-transparency"
                    if section["title"] == "Data Transparency Note"
                    else "zone-brief-paragraph"
                )
                parts.append(f'<p class="{css_class}">{html.escape(line)}</p>')
        parts.append("</div>")
    parts.append("</div>")
    return "\n".join(parts)


def _format_relevance_score(score) -> str:
    if score is None:
        return "—"
    try:
        return f"{float(score):.3f}"
    except (TypeError, ValueError):
        return "—"


def _truncate_text(text: str, limit: int) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def build_compact_rag_summary(rag_context: dict) -> str:
    """Return a short stakeholder-friendly RAG summary for the dashboard card."""
    country = (rag_context.get("country") or "this zone").strip()
    items = rag_context.get("retrieved_context") or []
    country_specific = [item for item in items if not item.get("is_fallback")]
    fallback = [item for item in items if item.get("is_fallback")]

    if not items:
        return ""

    parts: list[str] = []
    if country_specific:
        count = len(country_specific)
        source_label = "source" if count == 1 else "sources"
        parts.append(f"Country-specific context found for {country} ({count} {source_label}).")
    else:
        parts.append(f"No country-specific context found for {country}.")

    if fallback:
        fallback_count = len(fallback)
        fallback_label = "source" if fallback_count == 1 else "sources"
        parts.append(
            f"{fallback_count} fallback {fallback_label} included as general humanitarian context only."
        )

    return " ".join(parts)


def build_retrieved_crisis_context_text(rag_context: dict | None) -> list[str]:
    """Return plain-text lines for copy/PDF export."""
    lines = ["Retrieved Crisis Context", ""]

    if rag_context is None:
        lines.append(RAG_UNAVAILABLE_MESSAGE)
        return lines

    compact_summary = build_compact_rag_summary(rag_context)
    if compact_summary:
        lines.append(compact_summary)
    elif not (rag_context.get("retrieved_context") or []):
        lines.append(RAG_EMPTY_MESSAGE)

    transparency = (rag_context.get("transparency_note") or RAG_TRANSPARENCY_NOTE).strip()
    lines.append(transparency)
    lines.append("")

    items = (rag_context.get("retrieved_context") or [])[:3]
    if items:
        lines.append("Sources:")
        for item in items:
            title = _truncate_text(item.get("title") or "Untitled source", 160)
            lines.append(f"- {title}")
            url = (item.get("url") or "").strip()
            if url:
                lines.append(f"  {url}")

    return lines


def _safe_markdown_text(text: str) -> str:
    """Escape characters that would break simple Streamlit markdown."""
    return text.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")


def _render_rag_source_card(item: dict, add_divider: bool = True) -> None:
    """Render one retrieved source inside the expander using clean Streamlit markdown."""
    is_fallback = bool(item.get("is_fallback"))
    label = "Fallback / General Context" if is_fallback else "Country-Specific Context"

    meta_parts = [
        item.get("source_type") or "—",
        item.get("country") or "—",
    ]
    if item.get("event_type"):
        meta_parts.append(item.get("event_type"))

    title = _truncate_text(item.get("title") or "Untitled source", 140)
    preview = _truncate_text(item.get("preview") or "", 140)

    st.markdown(f"**{label}**")
    st.markdown(f"Relevance: {_format_relevance_score(item.get('relevance_score'))}")
    st.markdown(f"**{_safe_markdown_text(title)}**")
    st.caption(" · ".join(meta_parts))

    if is_fallback:
        st.caption("General context only; not direct evidence about this zone.")

    if preview:
        st.markdown(_safe_markdown_text(preview))

    url = (item.get("url") or "").strip()
    if url:
        st.markdown(f"[View source]({url})")

    if add_divider:
        st.divider()


def render_retrieved_crisis_context(rag_context: dict | None, zone_id: str = "") -> None:
    """Render the compact Retrieved Crisis Context section with a source expander."""
    st.markdown(
        """
        <div class="zone-brief-card rag-context-card">
            <div class="rag-context-title">Retrieved Crisis Context</div>
        """,
        unsafe_allow_html=True,
    )

    if rag_context is None:
        st.markdown(
            f'<p class="rag-context-warning">{html.escape(RAG_UNAVAILABLE_MESSAGE)}</p></div>',
            unsafe_allow_html=True,
        )
        return

    transparency = (rag_context.get("transparency_note") or RAG_TRANSPARENCY_NOTE).strip()
    items = rag_context.get("retrieved_context") or []
    compact_summary = build_compact_rag_summary(rag_context)

    summary_body = compact_summary
    if not summary_body and not items:
        summary_body = RAG_EMPTY_MESSAGE

    st.markdown(
        f"""
        <div class="rag-summary-card">
            <span class="rag-context-badge">Retrieval-Based Context</span>
            <p class="rag-summary-text">{html.escape(summary_body)}</p>
            <p class="rag-context-transparency">{html.escape(transparency)}</p>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if items:
        visible_items = items[:3]
        with st.expander("View retrieved sources", expanded=False):
            for index, item in enumerate(visible_items):
                _render_rag_source_card(
                    item,
                    add_divider=index < len(visible_items) - 1,
                )
        st.markdown('<div class="rag-expander-wrap"></div>', unsafe_allow_html=True)


def _clear_ai_brief_state() -> None:
    st.session_state["ai_brief_zone_id"] = None
    st.session_state["ai_brief_data"] = None
    st.session_state["ai_brief_requested"] = False


def render_ai_assisted_briefing_section(base_url: str, zone_id: str) -> None:
    """Render optional AI-assisted briefing generation for the selected zone."""
    st.markdown(
        f"""
        <div class="zone-brief-card ai-brief-card">
            <div class="rag-context-title">AI-Assisted Briefing</div>
            <p class="ai-brief-note">{html.escape(AI_BRIEF_NOTE)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "Generate AI-Assisted Brief",
        key=f"generate_ai_brief_{zone_id}",
        use_container_width=True,
    ):
        with st.spinner("Generating AI-assisted brief locally with Ollama..."):
            ai_data = get_ai_zone_briefing(base_url, zone_id)
        st.session_state["ai_brief_zone_id"] = zone_id
        st.session_state["ai_brief_data"] = ai_data
        st.session_state["ai_brief_requested"] = True

    if st.session_state.get("ai_brief_zone_id") != zone_id:
        return

    ai_data = st.session_state.get("ai_brief_data")
    if not ai_data:
        if st.session_state.get("ai_brief_requested"):
            st.warning(AI_BRIEF_UNAVAILABLE_MESSAGE)
        return

    model = ai_data.get("model") or "llama3.2"
    briefing_text = (ai_data.get("briefing_text") or "").strip()
    transparency_note = (ai_data.get("transparency_note") or AI_BRIEF_REVIEW_NOTE).strip()

    st.markdown(
        f"""
        <div class="zone-brief-card ai-brief-draft-card">
            <div class="ai-brief-draft-label">AI-Assisted Draft</div>
            <p class="ai-brief-meta">Model: {html.escape(str(model))} · Local Ollama</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if briefing_text:
        st.markdown('<div class="ai-brief-output-wrap">', unsafe_allow_html=True)
        st.markdown(briefing_text)
        st.markdown(
            f'<p class="ai-brief-transparency">{html.escape(transparency_note)}</p>',
            unsafe_allow_html=True,
        )


def _pdf_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def generate_zone_operational_brief_pdf(
    briefing: dict,
    rag_context: dict | None = None,
) -> bytes:
    """Generate an in-memory PDF for the Zone Operational Brief."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise ImportError(
            "PDF export requires reportlab. Install it with: pip install reportlab"
        ) from exc

    zone = briefing.get("zone", {})
    zone_name = zone.get("zone_name", "Unknown Zone")
    zone_id = zone.get("zone_id", "zone")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "BriefHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#1F4E79"),
        spaceAfter=6,
    )
    title_style = ParagraphStyle(
        "BriefTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.HexColor("#1F2933"),
        spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "BriefMeta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#667085"),
        spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "BriefSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=colors.HexColor("#1F4E79"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BriefBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    note_style = ParagraphStyle(
        "BriefNote",
        parent=body_style,
        fontSize=9,
        textColor=colors.HexColor("#667085"),
        spaceBefore=8,
    )

    story = [
        Paragraph(_pdf_escape("Crisis Resource Intelligence Network"), header_style),
        Paragraph(_pdf_escape("Zone Operational Brief"), title_style),
        Paragraph(
            _pdf_escape(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Zone: {zone_name} ({zone_id})"
            ),
            meta_style,
        ),
    ]

    for section in build_zone_operational_brief_sections(briefing):
        story.append(Paragraph(_pdf_escape(section["title"]), section_style))
        prefix = "• " if section["bullets"] else ""
        style = note_style if section["title"] == "Data Transparency Note" else body_style
        for line in section["lines"]:
            story.append(Paragraph(_pdf_escape(f"{prefix}{line}"), style))
        story.append(Spacer(1, 0.08 * inch))

    for line in build_retrieved_crisis_context_text(rag_context):
        if line == "Retrieved Crisis Context":
            story.append(Paragraph(_pdf_escape(line), section_style))
            continue
        if not line.strip():
            story.append(Spacer(1, 0.05 * inch))
            continue
        if line in {RAG_UNAVAILABLE_MESSAGE, RAG_EMPTY_MESSAGE}:
            style = note_style
        elif "retrieval-based context" in line.lower():
            style = note_style
        else:
            style = body_style
        story.append(Paragraph(_pdf_escape(line), style))

    doc.build(story)
    return buffer.getvalue()


def try_generate_zone_operational_brief_pdf(
    briefing: dict,
    rag_context: dict | None = None,
) -> tuple[bytes | None, str | None]:
    """Return PDF bytes, or (None, error_message) if generation is unavailable."""
    try:
        return generate_zone_operational_brief_pdf(briefing, rag_context), None
    except ImportError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"PDF generation failed: {exc}"


def _init_map_briefing_state() -> None:
    """Initialize session state for map-based zone briefings."""
    if "selected_zone_id" not in st.session_state:
        st.session_state["selected_zone_id"] = None
    if "selected_zone_briefing" not in st.session_state:
        st.session_state["selected_zone_briefing"] = None
    if "show_zone_brief" not in st.session_state:
        st.session_state["show_zone_brief"] = False
    if "rag_context_zone_id" not in st.session_state:
        st.session_state["rag_context_zone_id"] = None
    if "rag_zone_context" not in st.session_state:
        st.session_state["rag_zone_context"] = None
    if "ai_brief_zone_id" not in st.session_state:
        st.session_state["ai_brief_zone_id"] = None
    if "ai_brief_data" not in st.session_state:
        st.session_state["ai_brief_data"] = None
    if "ai_brief_requested" not in st.session_state:
        st.session_state["ai_brief_requested"] = False


def _load_zone_briefing(base_url: str, zone_id: str) -> dict | None:
    """Fetch briefing and reset brief/copy visibility when the zone changes."""
    if zone_id != st.session_state.get("selected_zone_id"):
        st.session_state["selected_zone_id"] = zone_id
        st.session_state["show_zone_brief"] = False
        st.session_state["rag_context_zone_id"] = None
        st.session_state["rag_zone_context"] = None
        _clear_ai_brief_state()
        for key in list(st.session_state.keys()):
            if str(key).startswith("brief_action_status_"):
                del st.session_state[key]
        st.session_state["selected_zone_briefing"] = get_zone_briefing(base_url, zone_id)
    elif st.session_state.get("selected_zone_briefing") is None:
        st.session_state["selected_zone_briefing"] = get_zone_briefing(base_url, zone_id)
    return st.session_state.get("selected_zone_briefing")


def _load_rag_zone_context(base_url: str, zone_id: str) -> dict | None:
    """Fetch RAG context for the open brief, caching per selected zone."""
    cached_zone = st.session_state.get("rag_context_zone_id")
    if cached_zone == zone_id and "rag_zone_context" in st.session_state:
        return st.session_state["rag_zone_context"]

    rag_context = get_rag_zone_context(base_url, zone_id)
    st.session_state["rag_context_zone_id"] = zone_id
    st.session_state["rag_zone_context"] = rag_context
    return rag_context


def render_selected_zone_panel(briefing: dict) -> None:
    """Render the Selected Zone summary card."""
    zone = briefing.get("zone", {})
    metrics = briefing.get("summary_metrics", {})
    alert = briefing.get("related_alert")
    alert_title = alert.get("title") if alert else "No linked alert"
    country = zone.get("country") or "—"
    region = zone.get("admin_region") or "—"

    detail_items = [
        ("Zone Name", zone.get("zone_name") or "—"),
        ("Country / Region", f"{country} / {region}"),
        ("Population Estimate", format_number(zone.get("population_estimate"))),
        ("Highest Priority Score", format_number(metrics.get("highest_mismatch_score"))),
        ("Largest Shortage Gap", format_number(metrics.get("largest_shortage_gap"))),
        ("Most Urgent Level", metrics.get("most_urgent_level") or "—"),
        ("Related Alert", alert_title),
    ]

    items_html = "".join(
        f'<div class="zone-detail-item">'
        f'<span class="zone-detail-label">{html.escape(label)}</span>'
        f'<span class="zone-detail-value">{html.escape(str(value))}</span>'
        f"</div>"
        for label, value in detail_items
    )

    st.markdown(
        f"""
        <div class="zone-details-card">
            <div class="zone-details-title">Selected Zone</div>
            <div class="zone-details-grid">{items_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_zone_operational_brief_preview(
    briefing: dict,
    rag_context: dict | None = None,
    zone_id: str = "",
) -> None:
    """Render the formatted Zone Operational Brief preview card."""
    st.markdown(generate_zone_operational_brief_html(briefing), unsafe_allow_html=True)
    render_retrieved_crisis_context(rag_context, zone_id=zone_id)


def render_view_brief_button() -> None:
    """Render the primary View Operational Brief action below the Selected Zone card."""
    st.markdown('<div class="zone-brief-action-spacer"></div>', unsafe_allow_html=True)
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        st.markdown('<span class="zone-brief-actions-primary"></span>', unsafe_allow_html=True)
        if st.button("View Operational Brief", key="view_zone_brief_btn", use_container_width=True):
            st.session_state["show_zone_brief"] = True


def render_copy_button(text: str, label: str = "Copy Brief", zone_id: str = "") -> None:
    """Render a clipboard copy button inside a Streamlit HTML component."""
    from streamlit.components.v1 import html as embed_html

    safe_text = json.dumps(text)
    status_id = f"brief-action-status-{zone_id}"

    embed_html(
        f"""
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                height: 44px;
                overflow: hidden;
                font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }}
        </style>
        <button
            type="button"
            onclick='
                (function() {{
                    var statusId = {json.dumps(status_id)};
                    function findStatusEl() {{
                        var docs = [document];
                        try {{ docs.push(window.parent.document); }} catch (e) {{}}
                        try {{
                            if (window.parent.parent) {{
                                docs.push(window.parent.parent.document);
                            }}
                        }} catch (e) {{}}
                        for (var i = 0; i < docs.length; i++) {{
                            try {{
                                var el = docs[i].getElementById(statusId);
                                if (el) return el;
                            }} catch (e) {{}}
                        }}
                        return null;
                    }}
                    navigator.clipboard.writeText({safe_text}).then(function() {{
                        var el = findStatusEl();
                        if (el) el.innerText = "Brief copied to clipboard.";
                    }}).catch(function() {{
                        var el = findStatusEl();
                        if (el) el.innerText = "Copy failed. Please try again.";
                    }});
                }})();
            '
            style="
                width: 100%;
                height: 44px;
                min-height: 44px;
                padding: 0 1rem;
                margin: 0;
                background-color: #1F4E79;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 0.95rem;
                font-weight: 500;
                font-family: inherit;
                line-height: 1;
                display: flex;
                align-items: center;
                justify-content: center;
                box-sizing: border-box;
                cursor: pointer;
            "
        >
            {html.escape(label)}
        </button>
        """,
        height=46,
    )


def _mark_pdf_download_started(zone_id: str) -> None:
    st.session_state[f"brief_action_status_{zone_id}"] = "PDF downloaded."


def render_brief_secondary_actions(
    briefing: dict,
    zone_id: str,
    rag_context: dict | None = None,
) -> None:
    """Render PDF and copy actions after the brief preview is opened."""
    brief_text = generate_zone_operational_brief_text(briefing, rag_context)
    status_key = f"brief_action_status_{zone_id}"
    status_id = f"brief-action-status-{zone_id}"
    col1, col2 = st.columns(2, gap="large")

    with col1:
        pdf_bytes, pdf_error = try_generate_zone_operational_brief_pdf(briefing, rag_context)
        if pdf_bytes is not None:
            st.download_button(
                label="Download PDF",
                data=pdf_bytes,
                file_name=f"zone_operational_brief_{zone_id}.pdf",
                mime="application/pdf",
                key=f"map_brief_pdf_{zone_id}",
                use_container_width=True,
                on_click=_mark_pdf_download_started,
                args=(zone_id,),
            )
        elif pdf_error:
            st.warning(pdf_error)

    with col2:
        render_copy_button(brief_text, "Copy Brief", zone_id=zone_id)

    status_message = st.session_state.get(status_key, "")
    st.markdown(
        f'<div id="{status_id}" class="brief-action-status">{html.escape(status_message)}</div>',
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value, accent: str = "neutral") -> None:
    if value is None:
        display_value = "—"
    elif isinstance(value, float):
        display_value = f"{value:,.0f}" if value == int(value) else f"{value:,.1f}"
    elif isinstance(value, int):
        display_value = f"{value:,}"
    else:
        display_value = str(value)

    st.markdown(
        f"""
        <div class="metric-card metric-accent-{accent}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{display_value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_api_base() -> str:
    """Return the internal API base URL (not exposed in the UI)."""
    return API_BASE_URL


def show_backend_warning() -> None:
    st.warning(
        "Dashboard data is currently unavailable. "
        "Please ensure the local data service is running."
    )


def apply_chart_layout(fig, title: str, height: int = 440, x_title: str = "", y_title: str = ""):
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=COLOR_TEXT)),
        template=CHART_TEMPLATE,
        paper_bgcolor=CHART_PAPER,
        plot_bgcolor=CHART_BG,
        font=dict(color=COLOR_TEXT, size=12),
        margin=dict(l=20, r=20, t=52, b=20),
        height=height,
        xaxis=dict(
            title=x_title,
            gridcolor=COLOR_BORDER,
            zerolinecolor=COLOR_BORDER,
            title_font=dict(size=12, color=COLOR_SECONDARY),
            tickfont=dict(color=COLOR_SECONDARY),
        ),
        yaxis=dict(
            title=y_title,
            gridcolor=COLOR_BORDER,
            zerolinecolor=COLOR_BORDER,
            title_font=dict(size=12, color=COLOR_SECONDARY),
            tickfont=dict(color=COLOR_SECONDARY),
        ),
        legend=dict(bgcolor="rgba(255,255,255,0.95)", bordercolor=COLOR_BORDER, borderwidth=1),
    )
    return fig


def render_hero_header() -> None:
    """Render polished website-style hero section."""
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-eyebrow">Crisis Resource Intelligence Network</div>
            <div class="hero-title">Humanitarian Resource Coordination Dashboard</div>
            <p class="hero-subtitle">Crisis monitoring, resource gaps, and operational supply-demand intelligence</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_info_card(title: str, body_html: str) -> None:
    """Render a styled informational card."""
    st.markdown(
        f"""
        <div class="info-card">
            <div class="info-card-title">{title}</div>
            <div class="info-card-body">{body_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_how_it_works_section() -> None:
    """Render numbered workflow steps."""
    st.markdown('<div class="subsection-header">How It Works</div>', unsafe_allow_html=True)
    steps = [
        "Public crisis data is collected from GDACS and ReliefWeb.",
        "Reports and alerts are cleaned and stored in PostgreSQL.",
        "Simulated field resource data represents organizations, zones, inventory, and requests.",
        "The mismatch engine compares available supply against requested demand.",
        "Priority scores rank shortages by shortage gap and urgency.",
        "FastAPI exposes the analytics to the dashboard.",
    ]
    steps_html = "".join(
        f'<div class="step-card"><div class="step-num">{i}</div><p class="step-text">{text}</p></div>'
        for i, text in enumerate(steps, start=1)
    )
    st.markdown(f'<div class="steps-grid">{steps_html}</div>', unsafe_allow_html=True)


def render_data_sources_section() -> None:
    """Render data sources with public vs simulated transparency."""
    st.markdown('<div class="subsection-header">Data Sources</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="info-card">
            <div class="sources-grid">
                <div>
                    <div class="source-column-title">Live / Public API Sources</div>
                    <ul>
                        <li>GDACS disaster alerts</li>
                        <li>ReliefWeb humanitarian reports</li>
                    </ul>
                </div>
                <div>
                    <div class="source-column-title">Prototype Operational Data</div>
                    <ul>
                        <li>Simulated NGO resource inventory</li>
                        <li>Simulated zone-level resource requests</li>
                        <li>Simulated partner organization records</li>
                    </ul>
                </div>
            </div>
            <div class="transparency-note">
                Operational inventory and request data are simulated because real NGO supply
                inventories are not generally public. The schema and analytics workflow are
                designed to model realistic coordination use cases.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pipeline_section() -> None:
    """Render real-time API pipeline explanation."""
    st.markdown('<div class="subsection-header">Real-Time API Pipeline</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="info-card">
            <div class="info-card-body">
                The crisis alert and humanitarian report layers are pulled from public APIs.
                Running the ingestion scripts refreshes the latest GDACS and ReliefWeb data,
                after which the database, analytics engine, API, and dashboard update from
                the refreshed records.
            </div>
            <div class="pipeline-flow">
                GDACS / ReliefWeb APIs &rarr; Ingestion Scripts &rarr; PostgreSQL
                &rarr; Mismatch Engine &rarr; FastAPI &rarr; Dashboard
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_priority_score_section() -> None:
    """Explain how priority scores support resource prioritization."""
    st.markdown('<div class="subsection-header">How Priority Scores Work</div>', unsafe_allow_html=True)
    render_info_card(
        "Priority scoring for coordination",
        """
        <p>For each zone and resource type, the system compares available supply against
        requested demand to calculate a shortage gap. That gap is weighted by urgency level
        (low, medium, high, critical) to produce a priority score. Higher scores indicate
        shortages that may require earlier operational attention. Surplus zones are identified
        when available supply exceeds requested demand.</p>
        """,
    )


def render_content_card_start() -> None:
    st.markdown('<div class="content-card">', unsafe_allow_html=True)


def render_content_card_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_map_legend(present_statuses: set[str] | None = None) -> None:
    """Render custom legend from STATUS_COLOR_MAP (synced with map markers)."""
    legend_labels = [
        label
        for label in MAP_LEGEND_ORDER
        if present_statuses is None or label in present_statuses
    ]
    items_html = "".join(
        f'<span class="map-legend-item">'
        f'<span class="map-legend-dot" style="background:{STATUS_COLOR_MAP[label]};"></span>'
        f"{label}</span>"
        for label in legend_labels
    )
    st.markdown(f'<div class="map-legend-bar">{items_html}</div>', unsafe_allow_html=True)


def build_operational_map_figure(df: pd.DataFrame) -> go.Figure:
    """Build scatter geo map with explicit per-status marker colors."""
    max_marker_size = 24
    size_ref = 2.0 * df["marker_size"].max() / (max_marker_size ** 2)

    fig = go.Figure()
    for display_status, color in STATUS_COLOR_MAP.items():
        subset = df[df["display_status"] == display_status]
        if subset.empty:
            continue

        fig.add_trace(
            go.Scattergeo(
                lat=subset["latitude"],
                lon=subset["longitude"],
                mode="markers",
                name=display_status,
                marker=dict(
                    size=subset["marker_size"],
                    color=color,
                    sizemode="area",
                    sizeref=size_ref,
                    sizemin=4,
                    line=dict(width=0.6, color="#FFFFFF"),
                ),
                customdata=subset[["zone_id", "hover_text"]].values,
                hovertemplate="%{customdata[1]}<extra></extra>",
                showlegend=False,
            )
        )

    lat_pad = max(4, (df["latitude"].max() - df["latitude"].min()) * 0.35)
    lon_pad = max(8, (df["longitude"].max() - df["longitude"].min()) * 0.35)

    fig.update_geos(
        bgcolor=COLOR_BG,
        landcolor="#E8ECF1",
        oceancolor="#D9E2EC",
        coastlinecolor="#98A2B3",
        lakecolor="#D9E2EC",
        showcountries=True,
        countrycolor="#98A3B3",
        showland=True,
        projection_type="natural earth",
        lataxis_range=[df["latitude"].min() - lat_pad, df["latitude"].max() + lat_pad],
        lonaxis_range=[df["longitude"].min() - lon_pad, df["longitude"].max() + lon_pad],
        fitbounds="locations",
    )
    apply_chart_layout(fig, "Operational Resource Status by Zone", height=600)
    fig.update_layout(showlegend=False)
    return fig


def render_overview_tab(base_url: str) -> None:
    st.markdown('<div class="section-header">Situation Overview</div>', unsafe_allow_html=True)

    render_info_card(
        "About this Dashboard",
        """
        <p>This dashboard monitors public crisis alerts and humanitarian reports, combines them
        with simulated field resource data, and identifies where resource shortages or surplus
        capacity may exist. It is designed as a decision-support prototype for humanitarian
        coordination and resource prioritization workflows.</p>
        """,
    )

    overview = get_overview(base_url)
    if overview is None:
        show_backend_warning()
    else:
        st.markdown('<div class="subsection-header">Operational Snapshot</div>', unsafe_allow_html=True)

        row1 = st.columns(4)
        with row1[0]:
            render_metric_card("Crisis Zones", overview.get("total_zones"), "primary")
        with row1[1]:
            render_metric_card("Partner Organizations", overview.get("total_organizations"), "primary")
        with row1[2]:
            render_metric_card("Critical Needs", overview.get("critical_shortage_count"), "critical")
        with row1[3]:
            render_metric_card("Severe Needs", overview.get("severe_shortage_count"), "severe")

        row2 = st.columns(4)
        with row2[0]:
            render_metric_card("Available Surplus", overview.get("surplus_count"), "surplus")
        with row2[1]:
            render_metric_card("Disaster Alerts", overview.get("total_gdacs_alerts"), "neutral")
        with row2[2]:
            render_metric_card("Humanitarian Reports", overview.get("total_crisis_reports"), "neutral")
        with row2[3]:
            render_metric_card("Resource Gaps Tracked", overview.get("total_mismatch_records"), "primary")

    render_how_it_works_section()
    render_priority_score_section()
    render_data_sources_section()
    render_pipeline_section()


def render_critical_tab(base_url: str) -> None:
    st.markdown('<div class="section-header">Priority Needs</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ops-note">These records identify the highest-priority resource gaps '
        "based on shortage size and urgency.</div>",
        unsafe_allow_html=True,
    )

    data = get_critical_shortages(base_url)
    if data is None:
        show_backend_warning()
        return
    if not data:
        st.info("No critical needs identified in the current dataset.")
        return

    df = pd.DataFrame(data)
    top_country = df.groupby("country")["mismatch_score"].sum().idxmax() if not df.empty else "—"

    kpi_row = st.columns(4)
    with kpi_row[0]:
        render_metric_card("Critical Needs", len(df), "critical")
    with kpi_row[1]:
        render_metric_card("Highest Priority Score", df["mismatch_score"].max(), "critical")
    with kpi_row[2]:
        render_metric_card("Largest Gap", df["shortage_gap"].max(), "critical")
    with kpi_row[3]:
        render_metric_card("Most Affected Country", top_country, "severe")

    render_content_card_start()
    display_cols = [
        "zone_name", "country", "admin_region", "resource_type",
        "total_available", "total_needed", "shortage_gap", "shortage_ratio",
        "urgency_level", "mismatch_score", "status_label",
    ]
    st.dataframe(prepare_display_df(df[display_cols]), use_container_width=True, hide_index=True)
    render_content_card_end()

    chart_df = df.copy()
    chart_df["label"] = chart_df.apply(
        lambda row: build_zone_resource_label(row["zone_name"], row["resource_type"]),
        axis=1,
    )
    chart_df = chart_df.sort_values("mismatch_score", ascending=True).tail(12)

    render_content_card_start()
    fig = px.bar(
        chart_df,
        x="mismatch_score",
        y="label",
        orientation="h",
        color_discrete_sequence=[COLOR_CRITICAL],
    )
    apply_chart_layout(fig, "Highest Priority Resource Gaps", x_title="Priority Score", y_title="Zone / Resource")
    st.plotly_chart(fig, use_container_width=True)
    render_content_card_end()


def render_surplus_tab(base_url: str) -> None:
    st.markdown('<div class="section-header">Available Surplus</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ops-note">Surplus zones may represent possible redistribution sources '
        "depending on distance, access, and operational constraints.</div>",
        unsafe_allow_html=True,
    )

    data = get_surplus_resources(base_url)
    if data is None:
        show_backend_warning()
        return
    if not data:
        st.info("No available surplus identified in the current dataset.")
        return

    df = pd.DataFrame(data)
    df["surplus_amount"] = df["shortage_gap"].abs()
    top_resource_row = df.loc[df["surplus_amount"].idxmax()]
    main_resource = format_resource_label(df.groupby("resource_type")["surplus_amount"].sum().idxmax())

    kpi_row = st.columns(4)
    with kpi_row[0]:
        render_metric_card("Surplus Records", len(df), "surplus")
    with kpi_row[1]:
        render_metric_card("Largest Surplus", df["surplus_amount"].max(), "surplus")
    with kpi_row[2]:
        render_metric_card("Main Surplus Resource", main_resource, "surplus")
    with kpi_row[3]:
        render_metric_card("Top Surplus Zone", top_resource_row["zone_name"], "surplus")

    table_df = df[
        ["zone_name", "country", "resource_type", "total_available", "total_needed", "surplus_amount", "status_label"]
    ].copy()
    table_df = table_df.rename(columns={"surplus_amount": "shortage_gap"})

    render_content_card_start()
    st.dataframe(
        prepare_display_df(table_df, extra_labels={"shortage_gap": "Surplus"}),
        use_container_width=True,
        hide_index=True,
    )
    render_content_card_end()

    chart_df = df.copy()
    chart_df["label"] = chart_df.apply(
        lambda row: build_zone_resource_label(row["zone_name"], row["resource_type"]),
        axis=1,
    )
    chart_df = chart_df.sort_values("surplus_amount", ascending=True).tail(12)

    render_content_card_start()
    fig = px.bar(
        chart_df,
        x="surplus_amount",
        y="label",
        orientation="h",
        color_discrete_sequence=[COLOR_SURPLUS],
    )
    apply_chart_layout(
        fig,
        "Largest Available Surplus by Zone",
        x_title="Surplus Amount",
        y_title="Zone / Resource",
    )
    st.plotly_chart(fig, use_container_width=True)
    render_content_card_end()


def render_summary_tab(base_url: str) -> None:
    st.markdown('<div class="section-header">Resource Balance</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ops-note">Positive net gap indicates shortage pressure. '
        "Negative net gap indicates surplus capacity.</div>",
        unsafe_allow_html=True,
    )

    data = get_resource_summary(base_url)
    if data is None:
        show_backend_warning()
        return
    if not data:
        st.info("No resource balance data available.")
        return

    df = pd.DataFrame(data)
    render_content_card_start()
    st.dataframe(prepare_display_df(df), use_container_width=True, hide_index=True)
    render_content_card_end()

    chart_df = df.copy()
    chart_df["resource_label"] = chart_df["resource_type"].apply(format_resource_label)
    chart_df = chart_df.sort_values("total_shortage_gap", ascending=False)
    colors = [
        COLOR_CRITICAL if gap > 0 else COLOR_SURPLUS if gap < 0 else COLOR_STABLE
        for gap in chart_df["total_shortage_gap"]
    ]

    render_content_card_start()
    fig = px.bar(
        chart_df,
        x="resource_label",
        y="total_shortage_gap",
        color="resource_label",
        color_discrete_sequence=colors,
    )
    fig.update_layout(showlegend=False)
    apply_chart_layout(fig, "Resource Balance by Type", x_title="Resource Type", y_title="Net Gap")
    st.plotly_chart(fig, use_container_width=True)
    render_content_card_end()


def _zone_id_from_map_selection(selection) -> str | None:
    """Extract zone_id from a Plotly point selection when available."""
    if not selection:
        return None
    points = getattr(getattr(selection, "selection", None), "points", None)
    if not points:
        return None
    customdata = points[0].get("customdata")
    if not customdata:
        return None
    if isinstance(customdata, (list, tuple)) and customdata:
        return str(customdata[0])
    return None


def render_map_tab(base_url: str) -> None:
    st.markdown('<div class="section-header">Operational Map</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ops-note">Marker size reflects priority score. '
        "Select a zone to review briefing options.</div>",
        unsafe_allow_html=True,
    )

    _init_map_briefing_state()

    zones = get_zones(base_url)
    if zones is None:
        show_backend_warning()
        return
    if not zones:
        st.info("No zones are available for map briefing.")
        return

    zone_labels = [build_zone_dropdown_label(zone) for zone in zones]
    zone_lookup = {build_zone_dropdown_label(zone): zone["zone_id"] for zone in zones}
    zone_id_to_label = {zone["zone_id"]: build_zone_dropdown_label(zone) for zone in zones}

    data = get_mismatches(base_url)
    if data is None:
        show_backend_warning()
        return
    if not data:
        st.info("No operational map data available.")
        return

    df = pd.DataFrame(data)
    df = df.dropna(subset=["latitude", "longitude"])
    if df.empty:
        st.info("Zone coordinates are not available for map display.")
        return

    df["marker_size"] = df["mismatch_score"].clip(lower=1)
    df["resource_label"] = df["resource_type"].apply(format_resource_label)
    df["display_status"] = df["status_label"].apply(format_status_label)
    df["hover_text"] = df.apply(
        lambda row: (
            f"<b>Zone:</b> {row['zone_name']}<br>"
            f"<b>Country:</b> {row['country']}<br>"
            f"<b>Resource:</b> {row['resource_label']}<br>"
            f"<b>Status:</b> {row['display_status']}<br>"
            f"<b>Priority Score:</b> {row['mismatch_score']:.0f}<br>"
            f"<b>Gap:</b> {row['shortage_gap']}"
        ),
        axis=1,
    )

    present_statuses = set(df["display_status"].dropna().unique())
    render_map_legend(present_statuses)

    map_figure = build_operational_map_figure(df)
    map_event = st.plotly_chart(
        map_figure,
        use_container_width=True,
        key="operational_map_chart",
        on_select="rerun",
        selection_mode="points",
    )

    clicked_zone_id = _zone_id_from_map_selection(map_event)
    if clicked_zone_id and clicked_zone_id in zone_id_to_label:
        _load_zone_briefing(base_url, clicked_zone_id)

    current_zone_id = st.session_state.get("selected_zone_id")
    selector_index = (
        zone_labels.index(zone_id_to_label[current_zone_id])
        if current_zone_id in zone_id_to_label
        else None
    )

    selected_label = st.selectbox(
        "Select a zone to view briefing options",
        zone_labels,
        index=selector_index,
        placeholder="Choose a zone...",
        key="map_zone_selector",
    )

    if selected_label:
        selected_zone_id = zone_lookup[selected_label]
        briefing = _load_zone_briefing(base_url, selected_zone_id)
    else:
        briefing = None

    if briefing is None:
        if selected_label:
            show_backend_warning()
        return

    render_selected_zone_panel(briefing)

    if not st.session_state.get("show_zone_brief"):
        render_view_brief_button()
    else:
        zone_id = st.session_state["selected_zone_id"]
        rag_context = _load_rag_zone_context(base_url, zone_id)
        render_zone_operational_brief_preview(briefing, rag_context, zone_id=zone_id)
        render_ai_assisted_briefing_section(base_url, zone_id)
        render_brief_secondary_actions(briefing, zone_id, rag_context)


def main() -> None:
    inject_styles()
    api_base = get_api_base()
    render_hero_header()

    tabs = st.tabs([
        "Situation Overview",
        "Priority Needs",
        "Available Surplus",
        "Resource Balance",
        "Operational Map",
    ])

    with tabs[0]:
        render_overview_tab(api_base)
    with tabs[1]:
        render_critical_tab(api_base)
    with tabs[2]:
        render_surplus_tab(api_base)
    with tabs[3]:
        render_summary_tab(api_base)
    with tabs[4]:
        render_map_tab(api_base)


if __name__ == "__main__":
    main()
