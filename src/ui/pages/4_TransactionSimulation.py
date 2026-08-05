# src/ui/pages/4_TransactionSimulation.py
"""Transaction Simulation page.
Provides controls to start, pause, resume, and stop the real‑time simulation engine.
Shows progress and simulation speed.
"""

import streamlit as st
from src.security.auth import require_auth
from src.simulation import runner
from src.ml.data_loader import load_dataset
from src.logging.logger import get_logger

logger = get_logger(__name__)

def render():
    require_auth()
    st.title("🚀 Transaction Simulation")
    st.caption("Control the real‑time transaction feed and simulation parameters.")

    # Load dataset once to know total rows
    if "_sim_total_rows" not in st.session_state:
        try:
            df = load_dataset()
            st.session_state["_sim_total_rows"] = len(df)
        except Exception as e:
            logger.error(f"Failed to load dataset for simulation: {e}")
            st.error("Could not load transaction dataset.")
            return

    total = st.session_state["_sim_total_rows"]
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("Start"):
            runner.start_simulation()
            logger.info("Simulation started by user.")
    with col2:
        if st.button("Pause"):
            runner.pause_simulation()
            logger.info("Simulation paused by user.")
        if st.button("Resume"):
            runner.resume_simulation()
            logger.info("Simulation resumed by user.")
    with col3:
        if st.button("Stop"):
            runner.stop_simulation()
            logger.info("Simulation stopped by user.")

    # Speed control
    speed = st.slider("Simulation speed (x)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    runner.set_speed(speed)
    st.write(f"Current speed: **{speed:.1f}×**")

    # Progress bar
    progress = st.session_state.get("sim_index", 0) / total if total else 0
    st.progress(progress)
    st.write(f"Processed {st.session_state.get('sim_index', 0)} of {total} transactions.")

    # Run the simulation loop – this must be called on every rerun while running
    if st.session_state.get("sim_running", False) and not st.session_state.get("sim_paused", False):
        runner.run_loop()
