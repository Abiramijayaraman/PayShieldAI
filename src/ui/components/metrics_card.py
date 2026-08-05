# src/ui/components/metrics_card.py
"""Reusable metric card component.
Displays a title, a numeric value, and an optional delta.
"""
import streamlit as st

def metric_card(title: str, value, delta=None, help_text: str = None):
    """Render a Streamlit metric card.
    Args:
        title: Card title.
        value: Numeric or string value to display.
        delta: Optional delta string (e.g., "+5%")
        help_text: Optional tooltip description.
    """
    col = st.columns(1)[0]
    with col:
        if help_text:
            st.caption(help_text)
        st.metric(label=title, value=value, delta=delta)
