import streamlit as st
import sys
import os
import io
import contextlib
import time
from datetime import datetime

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import system components
from profile_system.profile import EntityTracker
from profile_system.unsupervised import Clustering, AnomalyDetection
from profile_system.nlp import NLPProcessor
from profile_system.hitl import HITLFeedback
from profile_system.logging_viz import log_event, Visualizer
from profile_system.cli import ProfileSystemCLI

# Page Configuration
st.set_page_config(
    page_title="Profile System Terminal",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Premium Terminal Look
st.markdown("""
<style>
    /* Global Styles */
    @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;700&family=Inter:wght@400;600&display=swap');

    .stApp {
        background-color: #1a1b1e; /* Dark Charcoal */
        font-family: 'Inter', sans-serif;
    }

    /* Terminal Pane Styling */
    .terminal-container {
        font-family: 'Fira Code', monospace;
        background-color: #0e1117;
        color: #e6e6e6;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #30363d;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
        height: 60vh;
        overflow-y: auto;
    }

    .command-line {
        color: #5af; /* Soft Cyan/Blue */
        font-weight: 500;
    }

    .output-text {
        color: #c9d1d9;
        white-space: pre-wrap;
    }

    .success-msg { color: #7ee787; } /* Muted Green */
    .error-msg { color: #ff7b72; } /* Soft Red */
    .warning-msg { color: #d2a8ff; } /* Purple/Amber-ish replacement for contrast */
    .info-msg { color: #a5d6ff; } /* Muted Blue */

    /* Input Styling */
    .stTextInput > div > div > input {
        background-color: #0d1117;
        color: #c9d1d9;
        font-family: 'Fira Code', monospace;
        border: 1px solid #30363d;
    }
    .stTextInput > div > div > input:focus {
        border-color: #58a6ff;
        box-shadow: 0 0 0 1px #58a6ff;
    }

    /* Sidebar Styling */
    .css-1d391kg {
        background-color: #21262d;
    }
    
    .sidebar-stats {
        background: #161b22;
        padding: 10px;
        border-radius: 6px;
        margin-bottom: 10px;
        border: 1px solid #30363d;
    }

    /* Button Styling */
    .stButton > button {
        background-color: #238636;
        color: white;
        border: none;
        border-radius: 6px;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
    }
    .stButton > button:hover {
        background-color: #2ea043;
    }

</style>
""", unsafe_allow_html=True)

# Initialize Session State
if 'system' not in st.session_state:
    # Initialize the CLI class but we will use its components manually or wrapped
    # We need to persist the core logic objects
    st.session_state.system = ProfileSystemCLI()
    st.session_state.history = [] # List of (command, output, timestamp)
    st.session_state.input_key = 0 # key to reset input

# Helper function to execute command and capture output
def execute_command(command: str):
    if not command:
        return
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    # Capture stdout
    f = io.StringIO()
    try:
        with contextlib.redirect_stdout(f):
            # We assume process_command handles the logic and prints
            st.session_state.system.process_command(command)
        output = f.getvalue()
        status = "success"
        if "✖" in output: status = "error"
        elif "⚠" in output: status = "warning"
    except Exception as e:
        output = f"✖ Error executing command: {str(e)}"
        status = "error"
    
    st.session_state.history.append({
        "time": timestamp,
        "cmd": command,
        "out": output,
        "status": status
    }) 

# Sidebar Components
with st.sidebar:
    st.title("Context Sidebar")
    
    # Active System Stats
    tracker = st.session_state.system.tracker
    profile_count = len(tracker.profiles)
    
    st.markdown(f"""
    <div class="sidebar-stats">
        <strong>System Status</strong><br>
        <span style="color:#7ee787">● Online</span><br>
        Profiles Tracked: {profile_count}<br>
        Mode: {st.session_state.system.current_mode.upper()}
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.system.tracker.profiles:
        st.subheader("Active Profiles")
        selected_profile = st.selectbox("Select Profile", list(tracker.profiles.keys()))
        if selected_profile:
            p = tracker.profiles[selected_profile]
            st.json(p.to_dict())
            
            if st.button("Visualize Timeline"):
                events = p.behavioral_log
                if events:
                    st.line_chart([e.get('amount', 0) for e in events])
                else:
                    st.info("No numeric events to plot.")

# Main Interface
col1, col2 = st.columns([8, 2])
with col1:
    st.title("Profile System Terminal_")

with col2:
    # Utility buttons
    if st.button("Clear History", use_container_width=True):
        st.session_state.history = []

# Terminal Output Display
terminal_placeholder = st.empty()

with terminal_placeholder.container():
    terminal_html = '<div class="terminal-container">'
    
    if not st.session_state.history:
         terminal_html += """
         <div class="output-text">
         Welcome to Profile System v1.0 <br>
         Type 'help' to see available commands.
         </div>
         """

    for item in st.session_state.history:
        # Command line
        terminal_html += f"""
        <div class="command-line">
            <span style="color: #8b949e; margin-right: 8px;">{item['time']}</span>
            <span style="color: #7ee787;">➜</span> {item['cmd']}
        </div>
        """
        
        # Output
        out = item['out']
        context_class = ""
        if item['status'] == 'error': context_class = "error-msg"
        elif item['status'] == 'warning': context_class = "warning-msg"
        elif item['status'] == 'success': context_class = "success-msg"
        
        # Escape HTML in output to prevent injection/breaking layout (basic)
        out = out.replace("<", "&lt;").replace(">", "&gt;")
        
        terminal_html += f'<div class="output-text {context_class}">{out}</div><br>'
        
    terminal_html += '</div>'
    
    st.markdown(terminal_html, unsafe_allow_html=True)
    
    # JavaScript to auto-scroll to bottom of terminal
    st.components.v1.html(
        """
        <script>
            var terminals = window.parent.document.getElementsByClassName('terminal-container');
            if (terminals.length > 0) {
                terminals[0].scrollTop = terminals[0].scrollHeight;
            }
        </script>
        """, 
        height=0
    )

# Command Input
# Uses a form to allow 'Enter' to submit
with st.container():
    with st.form(key='cmd_form', clear_on_submit=True):
        user_input = st.text_input(
            "", 
            placeholder="Enter command (e.g., 'profile CUST-1', 'help')...",
            key="cmd_input"
        )
        submit_button = st.form_submit_button("Run")

    if submit_button and user_input:
        execute_command(user_input)
        st.rerun()

# Auto-scroll js hack (optional, but helps terminal feel)
# Streamlit scrolls to top by default on rerun, which is annoying for terminals.
# We can try to keep position or just let it be. 
