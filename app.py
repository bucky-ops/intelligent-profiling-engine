"""Enhanced Streamlit Web Dashboard for the Intelligent Profiling Engine.

Multi-section interactive dashboard with:
  📊 Dashboard  - overview KPIs + summary charts
  💻 Terminal   - command REPL with history
  👥 Profiles   - searchable profile table + detail inspector
  📈 Analytics  - clustering + anomaly detection with interactive Plotly charts
  ✅ HITL       - validation review queue
  📁 Data       - import / export profiles

All sections share the same Profiler service instance (persisted in
st.session_state) so changes made in one section are immediately visible
in the others.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from datetime import datetime

import streamlit as st

# Ensure src is importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from profile_system.cli import ProfileSystemCLI, Profiler  # noqa: E402

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Intelligent Profiling Engine",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;700&family=Inter:wght@400;600;700&display=swap');

    .stApp { font-family: 'Inter', sans-serif; }

    /* KPI cards */
    .kpi-card {
        background: linear-gradient(135deg, #161b22 0%, #21262d 100%);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #30363d;
        text-align: center;
        transition: transform 0.2s;
    }
    .kpi-card:hover { transform: translateY(-2px); border-color: #58a6ff; }
    .kpi-label { color: #8b949e; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-value { font-size: 2.2rem; font-weight: 700; margin: 8px 0; }
    .kpi-sub { color: #8b949e; font-size: 0.8rem; }

    /* Terminal */
    .terminal-container {
        font-family: 'Fira Code', monospace;
        background-color: #0e1117;
        color: #e6e6e6;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid #30363d;
        height: 50vh;
        overflow-y: auto;
        font-size: 0.85rem;
    }
    .cmd-line { color: #58a6ff; font-weight: 500; }
    .out-text { color: #c9d1d9; white-space: pre-wrap; }
    .out-success { color: #7ee787; }
    .out-error { color: #ff7b72; }
    .out-warning { color: #d2a8ff; }
    .timestamp { color: #8b949e; margin-right: 8px; font-size: 0.75rem; }

    /* Section headers */
    .section-header {
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0 0 16px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #30363d;
    }

    /* Profile detail */
    .profile-detail {
        background: #0e1117;
        color: #c9d1d9;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid #30363d;
        font-family: 'Fira Code', monospace;
        font-size: 0.8rem;
        max-height: 500px;
        overflow-y: auto;
    }

    /* Sidebar stats */
    .sidebar-stat {
        background: #161b22;
        padding: 10px 12px;
        border-radius: 6px;
        border: 1px solid #30363d;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ─── Session state initialization ──────────────────────────────────────────
@st.cache_resource
def get_profiler() -> Profiler:
    """Singleton profiler cached across reruns."""
    storage = os.environ.get("PROFILES_STORAGE_PATH", "profiles.json")
    return Profiler(storage_file=storage)


def get_cli() -> ProfileSystemCLI:
    if "cli" not in st.session_state:
        st.session_state.cli = ProfileSystemCLI(profiler=get_profiler())
    return st.session_state.cli


def init_state():
    if "history" not in st.session_state:
        st.session_state.history = []
    if "page" not in st.session_state:
        st.session_state.page = "📊 Dashboard"


init_state()
cli = get_cli()
profiler = cli.profiler


# ─── Helper: execute a CLI command and capture output ──────────────────────
def execute_command(command: str) -> tuple[str, str]:
    """Run a command, return (output_text, status)."""
    if not command:
        return "", "info"
    f = io.StringIO()
    try:
        with contextlib.redirect_stdout(f):
            cli.process_command(command)
        output = f.getvalue()
        if "✖" in output:
            status = "error"
        elif "⚠" in output:
            status = "warning"
        else:
            status = "success"
    except Exception as e:
        output = f"✖ Error: {e}"
        status = "error"
    st.session_state.history.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "cmd": command,
        "out": output,
        "status": status,
    })
    return output, status


# ─── Sidebar navigation ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧠 Intelligent Profiling Engine")
    st.caption("v0.3.0 · Hybrid ML + NLP + HITL")

    # Navigation
    pages = ["📊 Dashboard", "💻 Terminal", "👥 Profiles", "📈 Analytics", "✅ HITL", "📁 Data"]
    st.session_state.page = st.radio("Navigate", pages, label_visibility="collapsed")

    st.divider()

    # Live stats
    s = profiler.stats()
    st.markdown(f"""
    <div class="sidebar-stat">
        <strong>System Status</strong><br>
        <span style="color:#7ee787">● Online</span><br>
        <span class="timestamp">Profiles: {s['profile_count']}</span><br>
        <span class="timestamp">Signals: {s['total_behavioral_signals']}</span><br>
        <span class="timestamp">Mode: {cli.current_mode.upper()}</span>
    </div>
    """, unsafe_allow_html=True)

    # Quick actions
    st.divider()
    st.markdown("#### ⚡ Quick Actions")
    if st.button("🎲 Load Demo Data", use_container_width=True):
        for i in range(1, 11):
            profiler.update_profile(
                f"CUST-{i:03d}",
                {"behavioral": {"amount": float(i * 137.5), "frequency": float(i)}},
            )
        st.success("Loaded 10 demo profiles!")

    if st.button("🗑 Reset All", use_container_width=True):
        count = profiler.reset()
        st.warning(f"Removed {count} profiles")

    st.divider()
    st.caption("Built with ❤️ Streamlit + scikit-learn")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "📊 Dashboard":
    st.markdown('<p class="section-header">📊 Dashboard Overview</p>', unsafe_allow_html=True)

    # KPI cards
    s = profiler.stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Profiles Tracked</div>
            <div class="kpi-value" style="color:#7ee787">{s['profile_count']}</div>
            <div class="kpi-sub">{s['total_behavioral_signals']} total signals</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Avg Signals/Profile</div>
            <div class="kpi-value" style="color:#58a6ff">{s['avg_signals_per_profile']}</div>
            <div class="kpi-sub">{s['entities_with_text_insights']} with text insights</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">HITL Validations</div>
            <div class="kpi-value" style="color:#d2a8ff">{s['hitl_validations']}</div>
            <div class="kpi-sub">{s['hitl_overrides']} overrides</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        # Count anomalies
        anomaly_count = 0
        try:
            _, anomalies_df = profiler.detect_anomalies()
            anomaly_count = len(anomalies_df)
        except Exception:
            pass
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Anomalies Detected</div>
            <div class="kpi-value" style="color:#ff7b72">{anomaly_count}</div>
            <div class="kpi-sub">via Isolation Forest</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # Charts
    col_left, col_right = st.columns(2)
    df = profiler.tracker.get_profiles_df()

    with col_left:
        st.markdown("#### 💰 Total Amount per Profile")
        if not df.empty:
            st.bar_chart(df.set_index("entity_id")["total_amount"])
        else:
            st.info("No profiles yet. Load demo data from the sidebar.")

    with col_right:
        st.markdown("#### 📈 Signal Count Distribution")
        if not df.empty:
            st.bar_chart(df.set_index("entity_id")["signal_count"])
        else:
            st.info("No data to display.")

    st.divider()

    # Sentiment scatter
    st.markdown("#### 😊 Sentiment Polarity vs Subjectivity")
    if not df.empty and "sentiment_polarity" in df.columns:
        try:
            import plotly.express as px
            fig = px.scatter(
                df, x="sentiment_polarity", y="sentiment_subjectivity",
                size="signal_count", hover_name="entity_id",
                color="avg_amount", color_continuous_scale="Viridis",
                labels={"sentiment_polarity": "Polarity (-1 to 1)",
                        "sentiment_subjectivity": "Subjectivity (0 to 1)"},
                title="Sentiment Analysis Across Profiles",
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.scatter_chart(df, x="sentiment_polarity", y="sentiment_subjectivity")
    else:
        st.info("Run NLP analysis on profiles to see sentiment data.")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: TERMINAL
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "💻 Terminal":
    st.markdown('<p class="section-header">💻 Terminal</p>', unsafe_allow_html=True)

    # Terminal output
    terminal_html = '<div class="terminal-container">'
    if not st.session_state.history:
        terminal_html += """
        <div class="out-text">
        Welcome to Profile System v0.3.0<br>
        Type 'help' to see available commands.<br><br>
        Quick start:<br>
        &nbsp;&nbsp;profile CUST-1 update --behavior amount:100<br>
        &nbsp;&nbsp;cluster --n 3<br>
        &nbsp;&nbsp;analyze anomalies<br>
        &nbsp;&nbsp;stats
        </div>
        """
    for item in st.session_state.history[-50:]:  # last 50
        status_class = {
            "success": "out-success", "error": "out-error",
            "warning": "out-warning", "info": "out-text",
        }.get(item["status"], "out-text")
        out = item["out"].replace("<", "&lt;").replace(">", "&gt;")
        terminal_html += f"""
        <div class="cmd-line">
            <span class="timestamp">{item['time']}</span>
            <span style="color:#7ee787">➜</span> {item['cmd']}
        </div>
        <div class="out-text {status_class}">{out}</div>
        """
    terminal_html += "</div>"
    st.markdown(terminal_html, unsafe_allow_html=True)

    # Auto-scroll
    st.components.v1.html(
        """<script>
        var t = window.parent.document.getElementsByClassName('terminal-container');
        if (t.length > 0) { t[0].scrollTop = t[0].scrollHeight; }
        </script>""",
        height=0,
    )

    # Command input
    col_cmd, col_run = st.columns([5, 1])
    with col_cmd:
        user_input = st.text_input(
            "Command",
            placeholder="e.g., profile CUST-1 update --behavior amount:100",
            label_visibility="collapsed",
        )
    with col_run:
        if st.button("▶ Run", use_container_width=True):
            if user_input:
                execute_command(user_input)
                st.rerun()

    # Quick command buttons
    st.divider()
    st.markdown("#### ⚡ Quick Commands")
    qc1, qc2, qc3, qc4, qc5 = st.columns(5)
    if qc1.button("📊 Stats", use_container_width=True):
        execute_command("stats"); st.rerun()
    if qc2.button("📋 List", use_container_width=True):
        execute_command("list"); st.rerun()
    if qc3.button("🧮 Cluster", use_container_width=True):
        execute_command("cluster --n 3"); st.rerun()
    if qc4.button("⚠ Analyze", use_container_width=True):
        execute_command("analyze anomalies"); st.rerun()
    if qc5.button("🗑 Clear History", use_container_width=True):
        st.session_state.history = []
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# PAGE: PROFILES
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "👥 Profiles":
    st.markdown('<p class="section-header">👥 Profiles</p>', unsafe_allow_html=True)

    df = profiler.tracker.get_profiles_df()

    # Add profile form
    with st.expander("➕ Add / Update Profile", expanded=df.empty):
        with st.form("add_profile_form"):
            c1, c2, c3 = st.columns(3)
            eid = c1.text_input("Entity ID", placeholder="CUST-001")
            amount = c2.number_input("Amount", value=100.0, step=10.0)
            frequency = c3.number_input("Frequency", value=1, step=1)
            text = st.text_input("Text (optional, for NLP)",
                                 placeholder="Large transaction reported")
            submitted = st.form_submit_button("Add Profile")
            if submitted and eid:
                data = {"behavioral": {"amount": float(amount),
                                       "frequency": float(frequency)}}
                if text:
                    data["text"] = {"sentiment": profiler.nlp.sentiment_analysis(text)}
                profiler.update_profile(eid, data)
                st.success(f"✔ Profile updated for {eid}")
                st.rerun()

    st.divider()

    if df.empty:
        st.info("No profiles yet. Add one above or load demo data from the sidebar.")
    else:
        st.markdown("#### 📋 All Profiles")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_amount": st.column_config.NumberColumn(format="%.2f"),
                "avg_amount": st.column_config.NumberColumn(format="%.2f"),
                "sentiment_polarity": st.column_config.NumberColumn(format="%.3f"),
            },
        )

        # Profile detail inspector
        st.divider()
        st.markdown("#### 🔍 Profile Inspector")
        selected = st.selectbox("Select a profile", list(profiler.tracker.profiles.keys()))
        if selected:
            profile = profiler.tracker.profiles[selected]
            col_d1, col_d2 = st.columns([2, 1])
            with col_d1:
                st.markdown("**Profile JSON:**")
                st.json(profile.to_dict())
            with col_d2:
                st.markdown("**Behavioral Timeline:**")
                amounts = [s.get("amount", 0) for s in profile.behavioral_signals
                           if "amount" in s]
                if amounts:
                    st.line_chart(amounts, use_container_width=True)
                else:
                    st.info("No numeric signals.")

            # HITL validation for this profile
            st.divider()
            st.markdown("#### ✅ Add HITL Validation")
            notes = st.text_input("Notes", placeholder="e.g., legitimate customer")
            if st.button("Add Validation"):
                profiler.add_validation(selected, notes)
                st.success(f"✔ Validation added for {selected}")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "📈 Analytics":
    st.markdown('<p class="section-header">📈 Analytics</p>', unsafe_allow_html=True)

    df = profiler.tracker.get_profiles_df()
    if df.empty or len(df) < 3:
        st.warning("Need at least 3 profiles with data to run analytics. "
                   "Load demo data first.")
        st.stop()

    # Clustering
    st.markdown("#### 🧮 K-Means Clustering")
    n_clusters = st.slider("Number of clusters (K)", 2, 10, 3)
    if st.button("Run Clustering"):
        try:
            labels, summary_df = profiler.cluster(n_clusters=n_clusters)
            st.success(f"✔ Clustering complete: {len(labels)} profiles in {n_clusters} clusters")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            # Interactive scatter
            numeric = df.select_dtypes(include=["float64", "int64"])
            if numeric.shape[1] >= 2:
                try:
                    import plotly.express as px
                    df_plot = numeric.copy()
                    df_plot["cluster"] = labels
                    df_plot["entity_id"] = df["entity_id"]
                    fig = px.scatter(
                        df_plot, x=numeric.columns[0], y=numeric.columns[1],
                        color="cluster", hover_name="entity_id",
                        title="Cluster Visualization",
                        color_continuous_scale="Viridis",
                    )
                    fig.update_layout(height=450)
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    st.scatter_chart(numeric)
        except ValueError as e:
            st.error(f"⚠ {e}")

    st.divider()

    # Anomaly detection
    st.markdown("#### ⚠ Anomaly Detection (Isolation Forest)")
    contamination = st.slider("Contamination (expected anomaly fraction)",
                              0.01, 0.5, 0.1, 0.01)
    if st.button("Detect Anomalies"):
        try:
            scores, anomalies_df = profiler.detect_anomalies()
            if anomalies_df.empty:
                st.success("✔ No anomalies detected.")
            else:
                st.warning(f"⚠ Found {len(anomalies_df)} anomalies:")
                st.dataframe(anomalies_df, use_container_width=True, hide_index=True)

            # Score distribution
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.markdown("**Score Distribution:**")
                st.bar_chart(scores)
            with col_a2:
                st.markdown("**Anomaly vs Normal:**")
                normal = len(scores) - len(anomalies_df)
                st.metric("Normal", normal)
                st.metric("Anomalies", len(anomalies_df))
        except ValueError as e:
            st.error(f"⚠ {e}")

    st.divider()

    # Correlation heatmap
    st.markdown("#### 🔥 Feature Correlation")
    numeric_df = df.select_dtypes(include=["float64", "int64"])
    if numeric_df.shape[1] >= 2:
        corr = numeric_df.corr()
        try:
            import plotly.express as px
            fig = px.imshow(
                corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                title="Feature Correlation Matrix",
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.dataframe(corr)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: HITL
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "✅ HITL":
    st.markdown('<p class="section-header">✅ Human-in-the-Loop Review</p>',
                unsafe_allow_html=True)

    # Add validation form
    with st.form("hitl_form"):
        c1, c2 = st.columns([1, 3])
        entity_id = c1.text_input("Entity ID", placeholder="CUST-001")
        notes = c2.text_input("Notes", placeholder="e.g., confirmed legitimate")
        if st.form_submit_button("➕ Add Validation"):
            if entity_id:
                profiler.add_validation(entity_id, notes)
                st.success(f"✔ Validation added for {entity_id}")
                st.rerun()

    st.divider()

    # Validations table
    st.markdown("#### 📋 Validation Queue")
    validations = profiler.hitl.validations
    if not validations:
        st.info("No HITL validations yet. Add one above.")
    else:
        import pandas as pd
        val_df = pd.DataFrame(validations)
        st.dataframe(val_df, use_container_width=True, hide_index=True)

        # Summary
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Total Validations", len(validations))
        with c2:
            validated_count = sum(1 for v in validations if v.get("validated"))
            st.metric("Validated", validated_count)

        if st.button("🗑 Clear All Validations"):
            profiler.hitl.validations.clear()
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# PAGE: DATA
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "📁 Data":
    st.markdown('<p class="section-header">📁 Data Import / Export</p>',
                unsafe_allow_html=True)

    col_imp, col_exp = st.columns(2)

    with col_imp:
        st.markdown("#### 📥 Import Profiles")
        uploaded = st.file_uploader(
            "Upload CSV or JSON file",
            type=["csv", "json"],
        )
        if uploaded is not None:
            # Save to temp file then import
            suffix = os.path.splitext(uploaded.name)[1]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(uploaded.getvalue())
            tmp.close()
            try:
                count = profiler.import_profiles(tmp.name)
                st.success(f"✔ Imported {count} profiles from {uploaded.name}")
                st.rerun()
            except Exception as e:
                st.error(f"✖ Import failed: {e}")
            finally:
                os.unlink(tmp.name)

        st.markdown("""
        **CSV format:** `entity_id,amount,frequency,text` (text optional)

        **JSON format:** list of `{"entity_id": ..., "behavioral": {...}}`
        or a profiles.json export.
        """)

    with col_exp:
        st.markdown("#### 📤 Export Profiles")
        if profiler.tracker.profiles:
            fmt = st.selectbox("Format", ["JSON", "CSV"])
            if st.button("⬇ Export"):
                suffix = ".json" if fmt == "JSON" else ".csv"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp.close()
                try:
                    count = profiler.export_profiles(tmp.name)
                    with open(tmp.name, "rb") as f:
                        st.download_button(
                            label=f"⬇ Download {fmt} file",
                            data=f.read(),
                            file_name=f"profiles_export{suffix}",
                            mime="application/json" if fmt == "JSON" else "text/csv",
                        )
                    st.success(f"✔ Exported {count} profiles")
                except Exception as e:
                    st.error(f"✖ Export failed: {e}")
                finally:
                    os.unlink(tmp.name)
        else:
            st.info("No profiles to export.")

    st.divider()

    # Storage info
    st.markdown("#### 💾 Storage Info")
    s = profiler.stats()
    st.code(f"""Storage file: {s['storage_file']}
Profiles:      {s['profile_count']}
Signals:       {s['total_behavioral_signals']}
Validations:   {s['hitl_validations']}
Overrides:     {s['hitl_overrides']}""")

    # Danger zone
    st.divider()
    st.markdown("#### 🚨 Danger Zone")
    st.warning("Resetting will permanently delete all profiles and signals.")
    if st.button("🗑 Reset All Profiles", type="secondary"):
        count = profiler.reset()
        st.error(f"Removed {count} profiles.")
        st.rerun()
