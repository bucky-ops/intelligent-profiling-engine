"""Enhanced Tkinter desktop GUI for the Intelligent Profiling Engine.

Multi-tab interface:
  1. Terminal    - command REPL with autocomplete + command history
  2. Profiles    - sortable table of all profiles with detail inspector
  3. Analytics   - real-time matplotlib charts (cluster scatter, anomaly hist,
                   signal timeline)
  4. HITL        - human-in-the-loop validation review queue

Improvements over the original:
- Real-time auto-refreshing charts (polls the Profiler every 3 s).
- Sortable profile table (click column header to sort).
- Profile detail inspector panel showing JSON + behavioral timeline.
- Export/Import buttons in the toolbar.
- Status bar with live profile count + mode.
- Graceful shutdown (no os._exit).
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, font, messagebox, ttk
from typing import Optional

import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from profile_system.cli import ProfileSystemCLI  # noqa: E402

matplotlib.use("TkAgg")

# ─── Theme palette (GitHub dark inspired) ──────────────────────────────────
BG = "#1a1b1e"
PANEL = "#21262d"
PANEL_LIGHT = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
TEXT_DIM = "#8b949e"
ACCENT = "#58a6ff"
GREEN = "#7ee787"
RED = "#ff7b72"
AMBER = "#d2a8ff"
WHITE = "#ffffff"


class ConsoleRedirector:
    """Thread-safe stdout redirector into a Tk ``Text`` widget."""

    def __init__(self, check_func, text_widget, tag_stdout="stdout", tag_stderr="stderr"):
        self.text_widget = text_widget
        self.tag_stdout = tag_stdout
        self.tag_stderr = tag_stderr
        self.check_func = check_func

    def write(self, string):
        if not self.check_func():
            return
        self.text_widget.after(0, self._write, string)

    def _write(self, string):
        try:
            self.text_widget.configure(state="normal")
            tag = self.tag_stderr if "✖" in string or "⚠" in string else self.tag_stdout
            self.text_widget.insert("end", string, tag)
            self.text_widget.see("end")
            self.text_widget.configure(state="disabled")
        except tk.TclError:
            pass

    def flush(self):
        pass


class ProfileApp:
    """Main application window."""

    REFRESH_MS = 3000  # auto-refresh interval for charts

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Intelligent Profiling Engine — Desktop")
        self.root.geometry("1500x950")
        self.root.configure(bg=BG)
        self._configure_fonts()
        self._configure_styles()
        self.setup_ui()

        self.is_alive = True
        self._cmd_queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self.system = ProfileSystemCLI()
        self.original_stdout = sys.stdout
        sys.stdout = ConsoleRedirector(
            lambda: self.is_alive, self.term_text, "stdout", "stderr"
        )

        self.commands = [
            "profile", "cluster", "analyze", "visualize", "mode",
            "sidebar", "hitl", "help", "exit", "stats", "list",
            "import", "export", "reset", "nlp",
        ]
        self._cmd_history: list[str] = []
        self._history_idx = -1

        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

        # Kick off auto-refresh for charts + stats.
        self._schedule_refresh()

        print("Intelligent Profiling Engine v0.3.0 Initialized.")
        print("Type 'help' for commands. Try: profile CUST-1 update --behavior amount:100")

    # ─── Setup ───────────────────────────────────────────────────────────
    def _configure_fonts(self):
        self.font_mono = font.Font(family="Consolas", size=10)
        self.font_ui = font.Font(family="Segoe UI", size=10)
        self.font_title = font.Font(family="Segoe UI", size=14, weight="bold")
        self.font_small = font.Font(family="Segoe UI", size=9)

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TEXT, rowheight=24, font=self.font_small)
        style.configure("Treeview.Heading", background=BORDER, foreground=TEXT,
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BORDER, foreground=TEXT,
                        padding=[12, 6], font=self.font_ui)
        style.map("TNotebook.Tab",
                  background=[("selected", PANEL)],
                  foreground=[("selected", ACCENT)])
        style.configure("TButton", background=PANEL_LIGHT, foreground=TEXT,
                        bordercolor=BORDER, font=self.font_ui)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=self.font_ui)

    def setup_ui(self):
        # ─── Top toolbar ─────────────────────────────────────────────────
        toolbar = tk.Frame(self.root, bg=PANEL_LIGHT, height=40)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        tk.Label(toolbar, text=" 🧠 Intelligent Profiling Engine",
                 bg=PANEL_LIGHT, fg=ACCENT, font=self.font_title).pack(
            side=tk.LEFT, padx=15, pady=6)

        tk.Button(toolbar, text="📥 Import", bg=BG, fg=TEXT, relief=tk.FLAT,
                  font=self.font_small, padx=10, pady=2,
                  command=self._on_import).pack(side=tk.RIGHT, padx=5, pady=8)
        tk.Button(toolbar, text="📤 Export", bg=BG, fg=TEXT, relief=tk.FLAT,
                  font=self.font_small, padx=10, pady=2,
                  command=self._on_export).pack(side=tk.RIGHT, padx=5, pady=8)
        tk.Button(toolbar, text="🔄 Refresh", bg=BG, fg=TEXT, relief=tk.FLAT,
                  font=self.font_small, padx=10, pady=2,
                  command=self._refresh_all).pack(side=tk.RIGHT, padx=5, pady=8)

        # ─── Notebook with tabs ──────────────────────────────────────────
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))

        self._setup_terminal_tab()
        self._setup_profiles_tab()
        self._setup_analytics_tab()
        self._setup_hitl_tab()

        # ─── Status bar ──────────────────────────────────────────────────
        self.status_bar = tk.Frame(self.root, bg=PANEL_LIGHT, height=28)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.lbl_status = tk.Label(self.status_bar, text=" Ready",
                                   bg=PANEL_LIGHT, fg=TEXT_DIM, font=self.font_small,
                                   anchor=tk.W)
        self.lbl_status.pack(side=tk.LEFT, padx=10)
        self.lbl_profiles_count = tk.Label(self.status_bar, text="Profiles: 0",
                                           bg=PANEL_LIGHT, fg=GREEN,
                                           font=self.font_small)
        self.lbl_profiles_count.pack(side=tk.RIGHT, padx=10)
        self.lbl_mode = tk.Label(self.status_bar, text="Mode: ANALYSIS",
                                 bg=PANEL_LIGHT, fg=AMBER, font=self.font_small)
        self.lbl_mode.pack(side=tk.RIGHT, padx=10)

    # ─── Tab 1: Terminal ─────────────────────────────────────────────────
    def _setup_terminal_tab(self):
        frame = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(frame, text=" 💻 Terminal ")

        self.term_text = tk.Text(
            frame, bg="#0e1117", fg=TEXT, font=self.font_mono,
            insertbackground=WHITE, relief=tk.FLAT, padx=12, pady=12,
            state="disabled", wrap=tk.WORD,
        )
        self.term_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.term_text.tag_config("stdout", foreground=TEXT)
        self.term_text.tag_config("stderr", foreground=RED)
        self.term_text.tag_config("success", foreground=GREEN)
        self.term_text.tag_config("warning", foreground=AMBER)

        # Autocomplete popup
        self.suggestion_lb = tk.Listbox(
            self.root, bg=PANEL, fg=TEXT, font=self.font_mono,
            relief=tk.FLAT, selectbackground=ACCENT, selectforeground=WHITE,
        )
        self.suggestion_lb.bind("<<ListboxSelect>>", self._use_suggestion)

        # Input bar
        input_frame = tk.Frame(frame, bg=BG, height=36)
        input_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(input_frame, text="➜", bg=BG, fg=ACCENT,
                 font=("Consolas", 13, "bold")).pack(side=tk.LEFT, padx=(8, 4))
        self.cmd_entry = tk.Entry(
            input_frame, bg="#0d1117", fg=TEXT, font=self.font_mono,
            insertbackground=WHITE, relief=tk.FLAT, bd=1,
        )
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6,
                            padx=(0, 4))
        self.cmd_entry.config(highlightbackground=BORDER,
                              highlightcolor=ACCENT, highlightthickness=1)
        self.cmd_entry.bind("<Return>", self._on_enter)
        self.cmd_entry.bind("<Up>", self._on_history_up)
        self.cmd_entry.bind("<Down>", self._on_history_down)
        self.cmd_entry.bind("<KeyRelease>", self._check_autocomplete)
        self.cmd_entry.focus_set()

        # Clear button
        tk.Button(input_frame, text="Clear", bg=PANEL_LIGHT, fg=TEXT,
                  relief=tk.FLAT, font=self.font_small, padx=8,
                  command=self._clear_terminal).pack(side=tk.RIGHT, padx=4)

    # ─── Tab 2: Profiles ─────────────────────────────────────────────────
    def _setup_profiles_tab(self):
        frame = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(frame, text=" 👥 Profiles ")

        paned = tk.PanedWindow(frame, orient=tk.HORIZONTAL, bg=BG, sashwidth=4)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Left: table
        left = tk.Frame(paned, bg=BG)
        paned.add(left, minsize=500, stretch="always")

        cols = ("entity_id", "signals", "total_amount", "avg_amount", "sentiment", "updated")
        self.profile_tree = ttk.Treeview(left, columns=cols, show="headings")
        for c, label, w in [("entity_id", "Entity ID", 180), ("signals", "Signals", 70),
                            ("total_amount", "Total Amount", 110), ("avg_amount", "Avg Amount", 100),
                            ("sentiment", "Sentiment", 90), ("updated", "Updated", 150)]:
            self.profile_tree.heading(c, text=label,
                                      command=lambda c=c: self._sort_profile_tree(c))
            self.profile_tree.column(c, width=w, anchor=tk.W if c == "entity_id" else tk.E)
        vsb = ttk.Scrollbar(left, orient="vertical", command=self.profile_tree.yview)
        self.profile_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.profile_tree.pack(fill=tk.BOTH, expand=True)
        self.profile_tree.bind("<<TreeviewSelect>>", self._on_profile_select)

        # Right: detail inspector
        right = tk.Frame(paned, bg=PANEL)
        paned.add(right, minsize=450, stretch="always")

        tk.Label(right, text=" Profile Inspector", bg=PANEL, fg=ACCENT,
                 font=self.font_title, anchor=tk.W, padx=10, pady=8).pack(fill=tk.X)

        self.detail_text = tk.Text(right, bg="#0e1117", fg=TEXT, font=self.font_mono,
                                   relief=tk.FLAT, padx=10, pady=10, state="disabled",
                                   wrap=tk.WORD)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Mini chart canvas for selected profile's timeline
        self.detail_canvas_frame = tk.Frame(right, bg=PANEL)
        self.detail_canvas_frame.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))
        self.detail_canvas = None

    # ─── Tab 3: Analytics ────────────────────────────────────────────────
    def _setup_analytics_tab(self):
        frame = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(frame, text=" 📊 Analytics ")

        # Top row of stat cards
        stats_row = tk.Frame(frame, bg=BG)
        stats_row.pack(fill=tk.X, padx=8, pady=8)
        self.stat_cards: dict[str, tk.Label] = {}
        for key, label, color in [("profiles", "Profiles", GREEN),
                                  ("signals", "Signals", ACCENT),
                                  ("anomalies", "Anomalies", RED),
                                  ("validations", "HITL", AMBER)]:
            card = tk.Frame(stats_row, bg=PANEL_LIGHT, bd=1, relief=tk.SOLID)
            card.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
            tk.Label(card, text=label, bg=PANEL_LIGHT, fg=TEXT_DIM,
                     font=self.font_small).pack(pady=(6, 0))
            self.stat_cards[key] = tk.Label(card, text="0", bg=PANEL_LIGHT,
                                            fg=color, font=("Segoe UI", 22, "bold"))
            self.stat_cards[key].pack(pady=(0, 6))

        # Charts grid
        charts_frame = tk.Frame(frame, bg=BG)
        charts_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Cluster scatter (top-left)
        self.cluster_frame = tk.LabelFrame(charts_frame, text=" Cluster Scatter ",
                                           bg=PANEL, fg=TEXT, bd=1, relief=tk.SOLID,
                                           font=self.font_small)
        self.cluster_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Anomaly histogram (top-right)
        self.anomaly_frame = tk.LabelFrame(charts_frame, text=" Anomaly Score Distribution ",
                                           bg=PANEL, fg=TEXT, bd=1, relief=tk.SOLID,
                                           font=self.font_small)
        self.anomaly_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)

        # Signal timeline (bottom, full width)
        self.timeline_frame = tk.LabelFrame(charts_frame, text=" Signal Timeline (all entities) ",
                                            bg=PANEL, fg=TEXT, bd=1, relief=tk.SOLID,
                                            font=self.font_small)
        self.timeline_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)

        charts_frame.grid_rowconfigure(0, weight=1)
        charts_frame.grid_rowconfigure(1, weight=1)
        charts_frame.grid_columnconfigure(0, weight=1)
        charts_frame.grid_columnconfigure(1, weight=1)

        self.cluster_canvas = None
        self.anomaly_canvas = None
        self.timeline_canvas = None

    # ─── Tab 4: HITL ─────────────────────────────────────────────────────
    def _setup_hitl_tab(self):
        frame = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(frame, text=" ✅ HITL Review ")

        tk.Label(frame, text="Human-in-the-Loop Validation Queue",
                 bg=BG, fg=ACCENT, font=self.font_title).pack(pady=10)

        cols = ("entity_id", "validated", "notes", "time")
        self.hitl_tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, label, w in [("entity_id", "Entity ID", 200), ("validated", "Validated", 80),
                            ("notes", "Notes", 400), ("time", "Timestamp", 180)]:
            self.hitl_tree.heading(c, text=label)
            self.hitl_tree.column(c, width=w, anchor=tk.W)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.hitl_tree.yview)
        self.hitl_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=4)
        self.hitl_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Button(btn_frame, text="➕ Add Validation", bg=GREEN, fg=WHITE,
                  relief=tk.FLAT, font=self.font_small, padx=12, pady=4,
                  command=self._add_hitl).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="🗑 Clear", bg=PANEL_LIGHT, fg=TEXT,
                  relief=tk.FLAT, font=self.font_small, padx=12, pady=4,
                  command=self._clear_hitl).pack(side=tk.LEFT, padx=4)

    # ─── Command handling ────────────────────────────────────────────────
    def _on_enter(self, event):
        if self.suggestion_lb.winfo_ismapped():
            self._use_suggestion(None)
            return
        cmd = self.cmd_entry.get()
        if not cmd:
            return
        self.cmd_entry.delete(0, "end")
        self.suggestion_lb.place_forget()
        self._cmd_history.append(cmd)
        self._history_idx = len(self._cmd_history)

        self.term_text.configure(state="normal")
        self.term_text.insert("end", f"\n➜ {cmd}\n", "stdout")
        self.term_text.see("end")
        self.term_text.configure(state="disabled")
        self._cmd_queue.put(cmd)

    def _on_history_up(self, event):
        if not self._cmd_history:
            return
        self._history_idx = max(0, self._history_idx - 1)
        self.cmd_entry.delete(0, "end")
        self.cmd_entry.insert(0, self._cmd_history[self._history_idx])
        return "break"

    def _on_history_down(self, event):
        if not self._cmd_history:
            return
        self._history_idx = min(len(self._cmd_history), self._history_idx + 1)
        self.cmd_entry.delete(0, "end")
        if self._history_idx < len(self._cmd_history):
            self.cmd_entry.insert(0, self._cmd_history[self._history_idx])
        return "break"

    def _check_autocomplete(self, event):
        if event.keysym in ["Up", "Down", "Return"]:
            return
        typed = self.cmd_entry.get().split(" ")[-1]
        if not typed:
            self.suggestion_lb.place_forget()
            return
        matching = [c for c in self.commands if c.startswith(typed)]
        if matching:
            self.suggestion_lb.delete(0, tk.END)
            for m in matching:
                self.suggestion_lb.insert(tk.END, m)
            x = (self.cmd_entry.winfo_rootx() - self.root.winfo_rootx()
                 + (len(self.cmd_entry.get()) - len(typed)) * 8)
            y = self.cmd_entry.winfo_rooty() - self.root.winfo_rooty() + 32
            self.suggestion_lb.place(x=x, y=y, width=160, height=120)
            self.suggestion_lb.selection_set(0)
        else:
            self.suggestion_lb.place_forget()

    def _use_suggestion(self, event):
        if not self.suggestion_lb.curselection():
            return
        selected = self.suggestion_lb.get(self.suggestion_lb.curselection())
        words = self.cmd_entry.get().split(" ")
        words[-1] = selected
        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.insert(0, " ".join(words))
        self.suggestion_lb.place_forget()
        self.cmd_entry.focus_set()

    def _worker_loop(self):
        while self.is_alive:
            try:
                cmd = self._cmd_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if cmd is None:
                break
            try:
                self.system.process_command(cmd)
                self._refresh_all()
            except Exception as e:
                print(f"✖ Error: {e}")

    # ─── Data refresh ────────────────────────────────────────────────────
    def _schedule_refresh(self):
        if not self.is_alive:
            return
        self._refresh_all()
        self.root.after(self.REFRESH_MS, self._schedule_refresh)

    def _refresh_all(self):
        self.root.after(0, self._refresh_profiles_table)
        self.root.after(0, self._refresh_hitl_table)
        self.root.after(0, self._refresh_stats)
        self.root.after(0, self._refresh_charts)

    def _refresh_stats(self):
        try:
            s = self.system.profiler.stats()
            self.lbl_profiles_count.config(text=f"Profiles: {s['profile_count']}")
            self.lbl_mode.config(text=f"Mode: {self.system.current_mode.upper()}")
            self.stat_cards["profiles"].config(text=str(s["profile_count"]))
            self.stat_cards["signals"].config(text=str(s["total_behavioral_signals"]))
            self.stat_cards["validations"].config(text=str(s["hitl_validations"]))
        except Exception:
            pass

    def _refresh_profiles_table(self):
        try:
            self.profile_tree.delete(*self.profile_tree.get_children())
            df = self.system.profiler.tracker.get_profiles_df()
            if df.empty:
                return
            # Count anomalies
            anomaly_ids = set()
            try:
                _, anomalies_df = self.system.profiler.detect_anomalies()
                anomaly_ids = set(anomalies_df["entity_id"].tolist())
            except Exception:
                pass
            self.stat_cards["anomalies"].config(text=str(len(anomaly_ids)))

            for _, row in df.iterrows():
                eid = row["entity_id"]
                tag = "anomaly" if eid in anomaly_ids else ""
                self.profile_tree.insert("", "end", values=(
                    eid,
                    int(row.get("signal_count", 0)),
                    f"{row.get('total_amount', 0):.2f}",
                    f"{row.get('avg_amount', 0):.2f}",
                    f"{row.get('sentiment_polarity', 0):.3f}",
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ), tags=(tag,))
            self.profile_tree.tag_configure("anomaly", foreground=RED)
        except Exception:
            pass

    def _sort_profile_tree(self, col):
        items = [(self.profile_tree.set(k, col), k) for k in self.profile_tree.get_children("")]
        try:
            items.sort(key=lambda x: float(x[0]) if col not in ("entity_id",) else x[0])
        except ValueError:
            items.sort()
        for idx, (_, k) in enumerate(items):
            self.profile_tree.move(k, "", idx)

    def _on_profile_select(self, event):
        sel = self.profile_tree.selection()
        if not sel:
            return
        values = self.profile_tree.item(sel[0], "values")
        eid = values[0]
        profile = self.system.profiler.tracker.profiles.get(eid)
        if not profile:
            return
        # Update detail text
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", json.dumps(profile.to_dict(), indent=2, default=str))
        self.detail_text.configure(state="disabled")
        # Update mini chart
        self._draw_detail_chart(profile)

    def _draw_detail_chart(self, profile):
        for widget in self.detail_canvas_frame.winfo_children():
            widget.destroy()
        amounts = [s.get("amount", 0) for s in profile.behavioral_signals if "amount" in s]
        if not amounts:
            tk.Label(self.detail_canvas_frame, text="No numeric timeline data",
                     bg=PANEL, fg=TEXT_DIM, font=self.font_small).pack(pady=20)
            return
        fig = Figure(figsize=(5, 2.5), dpi=80)
        ax = fig.add_subplot(111)
        ax.plot(amounts, marker="o", linestyle="-", color=GREEN, markersize=4)
        ax.fill_between(range(len(amounts)), amounts, alpha=0.2, color=GREEN)
        ax.set_title(f"Amount Timeline: {profile.entity_id}", color=TEXT, fontsize=9)
        ax.set_xlabel("Event Index", fontsize=8)
        ax.set_ylabel("Amount", fontsize=8)
        ax.tick_params(colors=TEXT_DIM, labelsize=7)
        fig.patch.set_facecolor(PANEL)
        ax.set_facecolor(PANEL_LIGHT)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        fig.tight_layout()
        self.detail_canvas = FigureCanvasTkAgg(fig, master=self.detail_canvas_frame)
        self.detail_canvas.draw()
        self.detail_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _refresh_hitl_table(self):
        try:
            self.hitl_tree.delete(*self.hitl_tree.get_children())
            for v in self.system.profiler.hitl.validations:
                self.hitl_tree.insert("", "end", values=(
                    v.get("entity_id", ""),
                    "✔" if v.get("validated") else "✖",
                    v.get("notes", ""),
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ))
        except Exception:
            pass

    def _refresh_charts(self):
        try:
            self._draw_cluster_chart()
            self._draw_anomaly_chart()
            self._draw_timeline_chart()
        except Exception:
            pass

    def _draw_cluster_chart(self):
        for widget in self.cluster_frame.winfo_children():
            widget.destroy()
        df = self.system.profiler.tracker.get_profiles_df()
        if df.empty or len(df) < 3:
            tk.Label(self.cluster_frame, text="Need ≥3 profiles to cluster",
                     bg=PANEL, fg=TEXT_DIM, font=self.font_small).pack(pady=40)
            return
        try:
            labels, _ = self.system.profiler.cluster()
            numeric = df.select_dtypes(include=["float64", "int64"])
            if numeric.shape[1] >= 2:
                fig = Figure(figsize=(4, 3), dpi=80)
                ax = fig.add_subplot(111)
                ax.scatter(numeric.iloc[:, 0], numeric.iloc[:, 1],
                                     c=labels, cmap="viridis", s=30, alpha=0.8)
                ax.set_title("Cluster Scatter", color=TEXT, fontsize=9)
                ax.set_xlabel(numeric.columns[0], fontsize=8)
                ax.set_ylabel(numeric.columns[1], fontsize=8)
                ax.tick_params(colors=TEXT_DIM, labelsize=7)
                fig.patch.set_facecolor(PANEL)
                ax.set_facecolor(PANEL_LIGHT)
                for spine in ax.spines.values():
                    spine.set_color(BORDER)
                fig.tight_layout()
                canvas = FigureCanvasTkAgg(fig, master=self.cluster_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception:
            tk.Label(self.cluster_frame, text="Clustering not available",
                     bg=PANEL, fg=TEXT_DIM, font=self.font_small).pack(pady=40)

    def _draw_anomaly_chart(self):
        for widget in self.anomaly_frame.winfo_children():
            widget.destroy()
        df = self.system.profiler.tracker.get_profiles_df()
        if df.empty:
            tk.Label(self.anomaly_frame, text="No data for anomaly detection",
                     bg=PANEL, fg=TEXT_DIM, font=self.font_small).pack(pady=40)
            return
        try:
            scores, _ = self.system.profiler.detect_anomalies()
            fig = Figure(figsize=(4, 3), dpi=80)
            ax = fig.add_subplot(111)
            ax.hist(scores, bins=15, color=ACCENT, alpha=0.7, edgecolor=BORDER)
            ax.axvline(0, color=RED, linestyle="--", linewidth=1, label="anomaly threshold")
            ax.set_title("Anomaly Score Distribution", color=TEXT, fontsize=9)
            ax.set_xlabel("Score", fontsize=8)
            ax.set_ylabel("Count", fontsize=8)
            ax.tick_params(colors=TEXT_DIM, labelsize=7)
            ax.legend(fontsize=7, facecolor=PANEL_LIGHT, edgecolor=BORDER, labelcolor=TEXT)
            fig.patch.set_facecolor(PANEL)
            ax.set_facecolor(PANEL_LIGHT)
            for spine in ax.spines.values():
                spine.set_color(BORDER)
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self.anomaly_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception:
            tk.Label(self.anomaly_frame, text="Anomaly detection not available",
                     bg=PANEL, fg=TEXT_DIM, font=self.font_small).pack(pady=40)

    def _draw_timeline_chart(self):
        for widget in self.timeline_frame.winfo_children():
            widget.destroy()
        profiles = self.system.profiler.tracker.profiles
        if not profiles:
            tk.Label(self.timeline_frame, text="No profiles yet",
                     bg=PANEL, fg=TEXT_DIM, font=self.font_small).pack(pady=30)
            return
        fig = Figure(figsize=(8, 2.5), dpi=80)
        ax = fig.add_subplot(111)
        for eid, p in list(profiles.items())[:10]:  # top 10 to avoid clutter
            amounts = [s.get("amount", 0) for s in p.behavioral_signals if "amount" in s]
            if amounts:
                ax.plot(range(len(amounts)), amounts, marker="o", markersize=3,
                        label=eid[:12], alpha=0.7)
        ax.set_title("Signal Timeline (top 10 entities)", color=TEXT, fontsize=9)
        ax.set_xlabel("Event Index", fontsize=8)
        ax.set_ylabel("Amount", fontsize=8)
        ax.tick_params(colors=TEXT_DIM, labelsize=7)
        if profiles:
            ax.legend(fontsize=6, facecolor=PANEL_LIGHT, edgecolor=BORDER,
                      labelcolor=TEXT, ncol=5, loc="upper right")
        fig.patch.set_facecolor(PANEL)
        ax.set_facecolor(PANEL_LIGHT)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.timeline_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ─── Toolbar actions ─────────────────────────────────────────────────
    def _on_import(self):
        path = filedialog.askopenfilename(
            title="Import profiles",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            count = self.system.profiler.import_profiles(path)
            messagebox.showinfo("Import", f"Imported {count} profiles from {path}")
            self._refresh_all()
        except Exception as e:
            messagebox.showerror("Import failed", str(e))

    def _on_export(self):
        path = filedialog.asksaveasfilename(
            title="Export profiles",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv")],
        )
        if not path:
            return
        try:
            count = self.system.profiler.export_profiles(path)
            messagebox.showinfo("Export", f"Exported {count} profiles to {path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _clear_terminal(self):
        self.term_text.configure(state="normal")
        self.term_text.delete("1.0", tk.END)
        self.term_text.configure(state="disabled")

    def _add_hitl(self):
        # Simple dialog to add a validation
        win = tk.Toplevel(self.root)
        win.title("Add HITL Validation")
        win.geometry("400x180")
        win.configure(bg=BG)
        tk.Label(win, text="Entity ID:", bg=BG, fg=TEXT, font=self.font_ui).grid(
            row=0, column=0, padx=10, pady=10, sticky="w")
        eid_entry = tk.Entry(win, bg=PANEL_LIGHT, fg=TEXT, font=self.font_mono,
                              insertbackground=WHITE, relief=tk.FLAT)
        eid_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        tk.Label(win, text="Notes:", bg=BG, fg=TEXT, font=self.font_ui).grid(
            row=1, column=0, padx=10, pady=10, sticky="nw")
        notes_text = tk.Text(win, bg=PANEL_LIGHT, fg=TEXT, font=self.font_mono,
                             insertbackground=WHITE, relief=tk.FLAT, height=4, width=30)
        notes_text.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        def save():
            eid = eid_entry.get().strip()
            notes = notes_text.get("1.0", tk.END).strip()
            if eid:
                self.system.profiler.add_validation(eid, notes)
                print(f"✔ HITL validation added for {eid}")
                win.destroy()
                self._refresh_all()

        tk.Button(win, text="Save", bg=GREEN, fg=WHITE, relief=tk.FLAT,
                  font=self.font_ui, padx=20, pady=4, command=save).grid(
            row=2, column=0, columnspan=2, pady=10)
        win.grid_columnconfigure(1, weight=1)

    def _clear_hitl(self):
        self.system.profiler.hitl.validations.clear()
        self._refresh_hitl_table()

    # ─── Shutdown ────────────────────────────────────────────────────────
    def on_close(self):
        self.is_alive = False
        self._cmd_queue.put(None)
        try:
            self._worker.join(timeout=2.0)
        except RuntimeError:
            pass
        try:
            self.system.profiler.tracker.save_profiles()
        except Exception:
            pass
        sys.stdout = self.original_stdout
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ProfileApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
