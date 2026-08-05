# main.py
"""Streamlit entry point for PayShield AI.

It renders a sidebar navigation (using the existing navigation component) and dispatches to the selected page.
All pages are located under `src.ui.pages` and expose a `render()` function.
"""

import types, sys, importlib

# Stub starlette.middleware.gzip to avoid import errors in Streamlit
gzip_mod = types.ModuleType('starlette.middleware.gzip')
gzip_mod.DEFAULT_EXCLUDED_CONTENT_TYPES = []
sys.modules['starlette.middleware.gzip'] = gzip_mod

import streamlit as st
from src.ui.components.navigation import render_sidebar

# List of page titles shown in the sidebar (order defines display order)
PAGES = [
    "Login",
    "Dashboard",
    "Transaction Analysis",
    "Fraud Monitoring",
    "Simulation Lab",
    "Reports & History",
    "AI Fraud Assistant",
    "System",
]

# Mapping from page title to the Python module that implements the page
PAGE_MODULES = {
    "Login": "src.ui.pages.1_Login",
    "Dashboard": "src.ui.pages.dashboard",
    "Transaction Analysis": "src.ui.pages.transaction_analysis",
    "Fraud Monitoring": "src.ui.pages.fraud_monitoring",
    "Simulation Lab": "src.ui.pages.4_TransactionSimulation",
    "Reports & History": "src.ui.pages.reports_history",
    "AI Fraud Assistant": "src.ui.pages.9_Chatbot",
    "System": "src.ui.pages.system",
}

st.set_page_config(page_title="PayShield AI", layout="wide")

# Render the sidebar and retrieve the selected page title
selected = render_sidebar(PAGES)

# Load and render the selected page
module_name = PAGE_MODULES.get(selected)
if module_name:
    try:
        mod = importlib.import_module(module_name)
        if hasattr(mod, "render"):
            mod.render()
        else:
            st.error(f"The page module for '{selected}' does not have a render() function.")
    except Exception as e:
        st.error(f"Error loading page '{selected}': {e}")
        st.exception(e)
else:
    st.error(f"Page not found: {selected}")