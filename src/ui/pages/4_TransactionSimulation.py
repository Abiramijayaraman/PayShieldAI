# src/ui/pages/4_TransactionSimulation.py
"""Transaction Simulation page.

Provides controls to start, pause, resume, and stop the real-time
simulation engine. Shows progress, speed, and current simulation state.
"""

import streamlit as st

from src.logging.logger import get_logger
from src.ml.data_loader import load_dataset
from src.security.auth import require_auth
from src.simulation import runner


logger = get_logger(__name__)


def _get_simulation_status() -> str:
    """Return the current simulation state."""
    is_running = st.session_state.get(
        "sim_running",
        False,
    )

    is_paused = st.session_state.get(
        "sim_paused",
        False,
    )

    if is_running and is_paused:
        return "Paused"

    if is_running:
        return "Running"

    if st.session_state.get("sim_index", 0) > 0:
        return "Stopped"

    return "Ready"


def _render_status_message(status: str) -> None:
    """Render a status message matching the current state."""
    if status == "Running":
        st.success(
            "▶️ Simulation is currently running."
        )

    elif status == "Paused":
        st.warning(
            "⏸️ Simulation is currently paused."
        )

    elif status == "Stopped":
        st.info(
            "⏹️ Simulation is currently stopped."
        )

    else:
        st.info(
            "🚦 Simulation is ready to start."
        )


def _render_control_buttons() -> None:
    """Render simulation control buttons in one compact row."""
    start_col, pause_col, resume_col, stop_col = st.columns(4)

    with start_col:
        if st.button(
            "▶️ Start",
            use_container_width=True,
            key="simulation_start_button",
        ):
            runner.start_simulation()
            logger.info(
                "Simulation started by user."
            )
            st.rerun()

    with pause_col:
        if st.button(
            "⏸️ Pause",
            use_container_width=True,
            key="simulation_pause_button",
        ):
            runner.pause_simulation()
            logger.info(
                "Simulation paused by user."
            )
            st.rerun()

    with resume_col:
        if st.button(
            "⏯️ Resume",
            use_container_width=True,
            key="simulation_resume_button",
        ):
            runner.resume_simulation()
            logger.info(
                "Simulation resumed by user."
            )
            st.rerun()

    with stop_col:
        if st.button(
            "⏹️ Stop",
            use_container_width=True,
            key="simulation_stop_button",
        ):
            runner.stop_simulation()
            logger.info(
                "Simulation stopped by user."
            )
            st.rerun()


def _render_progress_metrics(
    processed: int,
    total: int,
    speed: float,
) -> None:
    """Render simulation metrics."""
    completion = (
        processed / total * 100
        if total
        else 0.0
    )

    status = _get_simulation_status()

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Status",
        status,
    )

    metric2.metric(
        "Processed",
        f"{processed:,}",
    )

    metric3.metric(
        "Total transactions",
        f"{total:,}",
    )

    metric4.metric(
        "Completion",
        f"{completion:.2f}%",
    )

    st.caption(
        f"Current simulation speed: {speed:.1f}×"
    )


def render():
    """Render the Transaction Simulation page."""
    require_auth()

    st.title("🚀 Transaction Simulation Lab")
    st.caption(
        "Control the real-time transaction feed, adjust processing speed, "
        "and monitor simulation progress."
    )

    if "_sim_total_rows" not in st.session_state:
        try:
            dataframe = load_dataset()

            st.session_state[
                "_sim_total_rows"
            ] = len(dataframe)

        except Exception as exc:
            logger.error(
                "Failed to load dataset for simulation: %s",
                exc,
            )

            st.error(
                "Could not load transaction dataset."
            )
            return

    total = st.session_state[
        "_sim_total_rows"
    ]

    processed = int(
        st.session_state.get(
            "sim_index",
            0,
        )
    )

    st.markdown("### Simulation controls")
    st.caption(
        "Use the controls below to start, pause, resume, or stop "
        "the transaction simulation."
    )

    _render_control_buttons()

    st.divider()

    st.markdown("### Simulation status")

    status = _get_simulation_status()
    _render_status_message(status)

    st.divider()

    st.markdown("### Speed and progress")

    speed = st.slider(
        "Simulation speed",
        min_value=0.1,
        max_value=5.0,
        value=1.0,
        step=0.1,
        help=(
            "Increase the value to process transactions faster."
        ),
    )

    runner.set_speed(speed)

    _render_progress_metrics(
        processed=processed,
        total=total,
        speed=speed,
    )

    progress = (
        processed / total
        if total
        else 0.0
    )

    progress = min(
        max(progress, 0.0),
        1.0,
    )

    st.progress(progress)

    st.caption(
        f"Processed {processed:,} of {total:,} transactions."
    )

    if (
        st.session_state.get(
            "sim_running",
            False,
        )
        and not st.session_state.get(
            "sim_paused",
            False,
        )
    ):
        runner.run_loop()