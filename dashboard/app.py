"""
Streamlit dashboard entry point.

Provides a starter UI for the Crisis Resource Intelligence Network.
Will later visualize shortages, surpluses, crisis maps, and ML predictions.

Run: streamlit run dashboard/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Crisis Resource Intelligence Network",
    page_icon="🌍",
    layout="wide",
)

st.title("Crisis Resource Intelligence Network")
st.caption("Week 1 setup — humanitarian crisis data, analytics, and resource intelligence")

st.markdown(
    """
    This dashboard will visualize:
    - Active humanitarian crises from ReliefWeb and GDACS
    - Resource supply vs. demand mismatches
    - Shortage risk predictions (ML, coming later)
    - Crisis assistant powered by RAG (coming later)
    """
)

col1, col2, col3 = st.columns(3)
col1.metric("Active Crises", "—", help="Populated once ingestion and DB are connected")
col2.metric("Resource Shortages", "—", help="Populated once mismatch engine is built")
col3.metric("Surplus Zones", "—", help="Populated once analytics queries are ready")

st.info(
    "Starter dashboard is running. Connect the FastAPI backend and PostgreSQL "
    "in upcoming weeks to populate live data."
)

with st.expander("Getting started"):
    st.markdown(
        """
        1. Run ingestion: `python -m ingestion.reliefweb_ingest`
        2. Start API: `uvicorn backend.main:app --reload`
        3. Open API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
        """
    )
