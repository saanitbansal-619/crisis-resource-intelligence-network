"""
Humanitarian Resource Coordination Dashboard — Crisis Resource Intelligence Network.

Consumes the FastAPI backend and presents crisis monitoring, resource gaps,
and supply-demand intelligence for NGO and field coordination workflows.

Run: streamlit run dashboard/app.py
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

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


def format_resource_label(resource_type: str) -> str:
    if not resource_type or pd.isna(resource_type):
        return ""
    return RESOURCE_LABELS.get(resource_type, str(resource_type).replace("_", " ").title())


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
            padding-top: 1rem;
            padding-bottom: 2.5rem;
            max-width: 1140px;
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
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            padding: 0.45rem 1rem;
        }}
        .stButton > button:hover {{
            background-color: #163d5e;
            color: white;
            border: none;
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
                customdata=subset["hover_text"],
                hovertemplate="%{customdata}<extra></extra>",
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


def render_map_tab(base_url: str) -> None:
    st.markdown('<div class="section-header">Operational Map</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ops-note">Zones are plotted by resource mismatch status. '
        "Marker size reflects priority score.</div>",
        unsafe_allow_html=True,
    )

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
    st.plotly_chart(build_operational_map_figure(df), use_container_width=True)


def main() -> None:
    st.set_page_config(
        page_title="Humanitarian Resource Coordination Dashboard",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

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
