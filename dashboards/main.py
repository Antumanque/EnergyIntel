import streamlit as st

st.set_page_config(
    page_title="EnergyIntel",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

from db import get_engine
from pages import cen, sea, overview

PAGES = {
    "Overview": overview,
    "CEN - Solicitudes": cen,
    "SEA - Proyectos": sea,
}

st.sidebar.title("EnergyIntel")
selection = st.sidebar.radio("", list(PAGES.keys()))

page = PAGES[selection]
page.render(get_engine())
