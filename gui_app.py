"""Tkinter desktop GUI for the Intelligent Profiling Engine.

Improvements over the original:
- Removes the unsafe ``os._exit(0)`` call on window close. We now signal the
  worker thread to stop, flush the profile store and destroy the Tk root
  cleanly so that ``atexit`` handlers and ``finally`` blocks run.
- ``GUIProfileSystem`` no longer duplicates ``handle_cluster`` / ``handle_analyze``
  logic. It delegates to the shared :class:`profile_system.cli.Profiler`
  service and only overrides *rendering* (table + plot callbacks).
- Argument parsing uses the same argparse parser as the CLI, so the GUI and
  CLI accept exactly the same command syntax.
"""
from __future__ import annotations

import queue
import sys
import threading
from typing import Optional

import matplotlib
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import font, ttk

# Ensure src is in python path (kept for backwards compatibility with the
# documented `python gui_app.py` entrypoint).
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from profile_system.cli import ProfileSystemCLI  # noqa: E402

matplotlib.use("TkAgg")


class GUIProfileSystem(ProfileSystemCLI):
    """Thin CLI subclass that routes results to Tk widgets.

    Inherits all business logic from :class:`ProfileSystemCLI` (which itself
    delegates to :class:`Profiler`), so the GUI cannot drift out of sync with
    the CLI anymore.
    """

    def __init__(self, table_callback, plot_callback):
        super().__init__()
        self.table_callback = table_callback
        self.plot_callback = plot_callback

    # ---- override the *rendering* hooks only, not the business logic -----
    def handle_cluster(self, args):
        try:
            _, summary_df = self.profiler.cluster(
                n_clusters=int(args[0]) if args and args[0].isdigit() else None
            )
        except ValueError as e:
            print(f"⚠ {e}")
            return
        except Exception as e:
            print(f"✖ Clustering failed: {e}")
            return

        print("✔ Clustering complete.")
        self.table_callback(summary_df)

        numeric_df = self.profiler.tracker.get_profiles_df().select_dtypes(
            include=["float64", "int64"]
        )
        if numeric_df.shape[1] >= 2 and len(numeric_df) == len(summary_df):
            fig = Figure(figsize=(5, 4), dpi=100)
            ax = fig.add_subplot(111)
            ax.scatter(
                numeric_df.iloc[:, 0], numeric_df.iloc[:, 1],
                c=summary_df["cluster"], cmap="viridis",
            )
            ax.set_title("Clusters Visualization")
            ax.set_xlabel(numeric_df.columns[0])
            ax.set_ylabel(numeric_df.columns[1])
            self.plot_callback(fig)

    def handle_analyze(self, args):
        if not args or args[0] != "anomalies":
            super().handle_analyze(args)
            return
        try:
            scores, anomalies_df = self.profiler.detect_anomalies()
        except ValueError as e:
            print(f"⚠ {e}")
            return
        except Exception as e:
            print(f"✖ Anomaly detection failed: {e}")
            return

        if not anomalies_df.empty:
            print(f"✔ Found {len(anomalies_df)} anomalies.")
            self.table_callback(anomalies_df)
        else:
            print("✔ No anomalies detected.")

        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        ax.hist(scores, bins=20, color="#58a6ff", alpha=0.7)
        ax.set_title("Anomaly Score Distribution")
        self.plot_callback(fig)

    def handle_visualize(self, args):
        if not args:
            print("⚠ Usage: visualize <entity_id>")
            return
        entity_id = args[0]
        try:
            profile = self.profiler.tracker.profiles[entity_id]
        except KeyError:
            print(f"⚠ Entity '{entity_id}' not found.")
            ids = list(self.profiler.tracker.profiles.keys())
            if ids:
                print(f"Available profiles: {', '.join(ids[:5])}"
                      + ("..." if len(ids) > 5 else ""))
            return

        amounts = [
            float(s.get("amount", 0))
            for s in profile.behavioral_signals
            if "amount" in s
        ]
        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        if amounts:
            ax.plot(amounts, marker="o", linestyle="-", color="#7ee787")
            ax.set_title(f"Transaction Amount History: {entity_id}")
            ax.set_xlabel("Event Index")
            ax.set_ylabel("Amount")
            print(f"✔ Visualizing timeline for {entity_id}")
        else:
            ax.text(
                0.5, 0.5, "No numeric timeline data available",
                ha="center", va="center", transform=ax.transAxes,
            )
            ax.set_title(f"Profile: {entity_id}")
            print("⚠ No numeric data to plot for this profile.")
        self.plot_callback(fig)

    def handle_profile(self, args):
        if not args:
            super().handle_profile(args)
            return

        # Support `profile update <ID> ...` syntax by re-ordering args.
        if args[0].lower() == "update" and len(args) > 1:
            args = [args[1], args[0]] + args[2:]

        if len(args) == 1:
            entity_id = args[0]
            profile = self.profiler.tracker.get_or_create_profile(entity_id)
            print(f"Loaded profile: {entity_id}")
            data = profile.to_dict()
            flat_data = [
                {"Field": k, "Value": f"[{len(v)} items]" if isinstance(v, list) else str(v)}
                for k, v in data.items()
            ] or [{"Field": "Status", "Value": "Empty Profile"}]
            self.table_callback(pd.DataFrame(flat_data))
        else:
            super().handle_profile(args)


class ConsoleRedirector:
    """Thread-safe stdout redirector that writes into a Tk ``Text`` widget."""

    def __init__(self, check_func, text_widget, tag_stdout, tag_stderr):
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
            self.text_widget.insert("end", string, self.tag_stdout)
            self.text_widget.see("end")
            self.text_widget.configure(state="disabled")
        except tk.TclError:
            # Widget already destroyed during shutdown - ignore silently.
            pass

    def flush(self):
        pass


class ProfileApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Profile System Terminal")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1a1b1e")

        self.font_mono = font.Font(family="Consolas", size=10)
        self.font_ui = font.Font(family="Segoe UI", size=10)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#21262d",
            fieldbackground="#21262d",
            foreground="#c9d1d9",
            rowheight=25,
        )
        style.configure(
            "Treeview.Heading",
            background="#30363d",
            foreground="#c9d1d9",
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Treeview", background=[("selected", "#58a6ff")])
        style.configure("TNotebook", background="#1a1b1e", borderwidth=0)
        style.configure(
            "TNotebook.Tab", background="#30363d", foreground="#c9d1d9", padding=[10, 5]
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#1a1b1e")],
            foreground=[("selected", "#58a6ff")],
        )

        self.setup_ui()

        self.is_alive = True
        # Thread-safe command queue: the UI thread enqueues, the worker
        # thread dequeues and executes. This lets us shut down gracefully.
        self._cmd_queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self.system = GUIProfileSystem(self.update_table, self.update_plot)
        self.original_stdout = sys.stdout
        sys.stdout = ConsoleRedirector(
            lambda: self.is_alive, self.term_text, "stdout", "stderr"
        )

        self.commands = [
            "profile", "cluster", "analyze", "visualize",
            "mode", "hitl", "help", "exit",
        ]

        # Start background worker.
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

        print("Profile System v1.0 Initialized.")
        print("Type 'help' for commands.")

    def setup_ui(self):
        main_pane = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, bg="#1a1b1e", sashwidth=4
        )
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = tk.Frame(main_pane, bg="#1a1b1e")
        main_pane.add(left_frame, minsize=400, stretch="always")

        self.term_text = tk.Text(
            left_frame, bg="#0e1117", fg="#c9d1d9", font=self.font_mono,
            insertbackground="white", relief=tk.FLAT, padx=10, pady=10,
            state="disabled",
        )
        self.term_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.term_text.tag_config("stdout", foreground="#c9d1d9")
        self.term_text.tag_config("stderr", foreground="#ff7b72")

        self.suggestion_lb = tk.Listbox(
            self.root, bg="#30363d", fg="#c9d1d9", font=self.font_mono, relief=tk.FLAT
        )
        self.suggestion_lb.bind("<<ListboxSelect>>", self.use_suggestion)

        input_frame = tk.Frame(left_frame, bg="#1a1b1e")
        input_frame.pack(fill=tk.X)

        tk.Label(
            input_frame, text="➜", bg="#1a1b1e", fg="#58a6ff",
            font=("Consolas", 12, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.cmd_entry = tk.Entry(
            input_frame, bg="#0d1117", fg="#c9d1d9", font=self.font_mono,
            insertbackground="white", relief=tk.FLAT, bd=1,
        )
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.cmd_entry.config(
            highlightbackground="#30363d", highlightcolor="#58a6ff", highlightthickness=1
        )
        self.cmd_entry.bind("<Return>", self.on_enter)
        self.cmd_entry.bind("<KeyRelease>", self.check_autocomplete)
        self.cmd_entry.bind("<Up>", self.nav_suggestion)
        self.cmd_entry.bind("<Down>", self.nav_suggestion)
        self.cmd_entry.focus_set()

        right_frame = tk.Frame(main_pane, bg="#21262d")
        main_pane.add(right_frame, minsize=400, stretch="always")

        self.stats_frame = tk.Frame(right_frame, bg="#161b22", bd=1, relief=tk.SOLID)
        self.stats_frame.pack(fill=tk.X, padx=10, pady=10)
        self.lbl_profiles = tk.Label(
            self.stats_frame, text="Profiles: 0", bg="#161b22", fg="#c9d1d9",
            font=("Segoe UI", 10),
        )
        self.lbl_profiles.pack(side=tk.LEFT, padx=10, pady=5)
        self.lbl_mode = tk.Label(
            self.stats_frame, text="Mode: ANALYSIS", bg="#161b22", fg="#7ee787",
            font=("Segoe UI", 10, "bold"),
        )
        self.lbl_mode.pack(side=tk.RIGHT, padx=10, pady=5)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.table_frame = tk.Frame(self.notebook, bg="#21262d")
        self.notebook.add(self.table_frame, text=" 📄 Data View ")

        y_scroll = ttk.Scrollbar(self.table_frame, orient="vertical")
        x_scroll = ttk.Scrollbar(self.table_frame, orient="horizontal")
        self.tree = ttk.Treeview(
            self.table_frame, columns=(), show="headings",
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set,
        )
        y_scroll.config(command=self.tree.yview)
        x_scroll.config(command=self.tree.xview)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.plot_frame = tk.Frame(self.notebook, bg="#21262d")
        self.notebook.add(self.plot_frame, text=" 📈 Visualization ")
        self.canvas = None

    # ----------------------------------------------------- autocomplete -----
    def check_autocomplete(self, event):
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
            x = (
                self.cmd_entry.winfo_rootx() - self.root.winfo_rootx()
                + (len(self.cmd_entry.get()) - len(typed)) * 8
            )
            y = self.cmd_entry.winfo_rooty() - self.root.winfo_rooty() + 30
            self.suggestion_lb.place(x=x, y=y, width=150, height=100)
            self.suggestion_lb.selection_set(0)
        else:
            self.suggestion_lb.place_forget()

    def nav_suggestion(self, event):
        if not self.suggestion_lb.winfo_ismapped():
            return
        cur_idx = self.suggestion_lb.curselection() or (0,)
        if event.keysym == "Up":
            new_idx = max(0, cur_idx[0] - 1)
        else:
            new_idx = min(self.suggestion_lb.size() - 1, cur_idx[0] + 1)
        self.suggestion_lb.selection_clear(0, tk.END)
        self.suggestion_lb.selection_set(new_idx)
        return "break"

    def use_suggestion(self, event):
        if not self.suggestion_lb.curselection():
            return
        selected = self.suggestion_lb.get(self.suggestion_lb.curselection())
        words = self.cmd_entry.get().split(" ")
        words[-1] = selected
        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.insert(0, " ".join(words))
        self.suggestion_lb.place_forget()
        self.cmd_entry.focus_set()

    # --------------------------------------------------------- commands -----
    def on_enter(self, event):
        if self.suggestion_lb.winfo_ismapped():
            self.use_suggestion(None)
            return
        cmd = self.cmd_entry.get()
        if not cmd:
            return
        self.cmd_entry.delete(0, "end")
        self.suggestion_lb.place_forget()

        self.term_text.configure(state="normal")
        self.term_text.insert("end", f"\n➜ {cmd}\n", "stdout")
        self.term_text.see("end")
        self.term_text.configure(state="disabled")

        self._cmd_queue.put(cmd)

    def _worker_loop(self):
        """Background worker that runs commands one at a time."""
        while self.is_alive:
            try:
                cmd = self._cmd_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if cmd is None:
                break
            try:
                self.system.process_command(cmd)
                self.update_stats()
            except Exception as e:
                print(f"✖ Error: {e}")

    # ------------------------------------------------------------- stats -----
    def update_stats(self):
        self.root.after(0, self._update_stats_ui)

    def _update_stats_ui(self):
        count = len(self.system.profiler.tracker.profiles)
        self.lbl_profiles.config(text=f"Profiles: {count}")
        self.lbl_mode.config(text=f"Mode: {self.system.current_mode.upper()}")

    # ------------------------------------------------------------ tables ----
    def update_table(self, df):
        self.root.after(0, self._update_table_ui, df)

    def _update_table_ui(self, df):
        self.notebook.select(self.table_frame)
        self.tree.delete(*self.tree.get_children())
        cols = list(df.columns)
        self.tree["columns"] = cols
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        for _, row in df.iterrows():
            self.tree.insert("", "end", values=[str(x) for x in row.tolist()])

    def update_plot(self, fig):
        self.root.after(0, self._update_plot_ui, fig)

    def _update_plot_ui(self, fig):
        self.notebook.select(self.plot_frame)
        for widget in self.plot_frame.winfo_children():
            widget.destroy()
        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # --------------------------------------------------------- shutdown -----
    def on_close(self):
        """Graceful shutdown: signal worker, flush store, destroy root."""
        self.is_alive = False
        self._cmd_queue.put(None)  # unblock the worker
        try:
            self._worker.join(timeout=2.0)
        except RuntimeError:
            pass
        # Flush any pending profile writes so profiles.json is not truncated.
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
