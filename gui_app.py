import tkinter as tk
from tkinter import ttk, font
import sys
import os
import threading
import io
import pandas as pd
from datetime import datetime
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Use TkAgg backend for embedding
matplotlib.use("TkAgg")

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from profile_system.cli import ProfileSystemCLI

class GUIProfileSystem(ProfileSystemCLI):
    def __init__(self, table_callback, plot_callback):
        super().__init__()
        self.table_callback = table_callback
        self.plot_callback = plot_callback

    def handle_cluster(self, args):
        df = self.tracker.get_profiles_df()
        if df.empty:
            print("⚠ No data to cluster. Create profiles first.")
            return

        numeric_df = df.select_dtypes(include=['float64', 'int64'])
        if numeric_df.empty or numeric_df.shape[0] < 3:
             print("⚠ Not enough numeric data (need 3+).")
             return

        try:
            labels = self.clustering.fit(numeric_df)
            df['cluster'] = labels
            print(f"✔ Clustering complete.")
            self.table_callback(df[['entity_id', 'cluster']])
            
            # Auto-visualize clusters if 2D/3D possible
            if numeric_df.shape[1] >= 2:
                fig = plt.Figure(figsize=(5, 4), dpi=100)
                ax = fig.add_subplot(111)
                ax.scatter(numeric_df.iloc[:, 0], numeric_df.iloc[:, 1], c=labels, cmap='viridis')
                ax.set_title("Clusters Visualization")
                ax.set_xlabel(numeric_df.columns[0])
                ax.set_ylabel(numeric_df.columns[1])
                self.plot_callback(fig)
                
        except Exception as e:
            print(f"✖ Clustering failed: {e}")

    def handle_analyze(self, args):
        if args and args[0] == 'anomalies':
            df = self.tracker.get_profiles_df()
            if df.empty:
                print("⚠ No data to analyze")
                return
            
            numeric_df = df.select_dtypes(include=['float64', 'int64'])
            if numeric_df.empty:
                print("⚠ No numeric data.")
                return

            try:
                scores = self.anomaly.fit(numeric_df)
                df['anomaly_score'] = scores
                anomalies = df[df['anomaly_score'] < 0]
                
                if not anomalies.empty:
                    print(f"✔ Found {len(anomalies)} anomalies.")
                    self.table_callback(anomalies[['entity_id', 'anomaly_score']])
                else:
                    print("✔ No anomalies detected.")
                
                # Visualize anomaly scores
                fig = plt.Figure(figsize=(5, 4), dpi=100)
                ax = fig.add_subplot(111)
                ax.hist(scores, bins=20, color='#58a6ff', alpha=0.7)
                ax.set_title("Anomaly Score Distribution")
                self.plot_callback(fig)

            except Exception as e:
                print(f"✖ Anomaly detection failed: {e}")
        else:
             super().handle_analyze(args)

    def handle_visualize(self, args):
        if not args:
            print("⚠ Usage: visualize <entity_id>")
            return
            
        entity_id = args[0]
        df = self.tracker.get_profiles_df()
        
        # Check for exact match
        if not df.empty and entity_id in df['entity_id'].values:
            target_id = entity_id
        # Check for case-insensitive match
        elif not df.empty and any(id.lower() == entity_id.lower() for id in df['entity_id'].values):
             target_id = next(id for id in df['entity_id'].values if id.lower() == entity_id.lower())
             print(f"ℹ Found '{target_id}' (matched case-insensitive).")
        else:
            print(f"⚠ Entity '{entity_id}' not found.")
            if not df.empty:
                ids = df['entity_id'].tolist()
                print(f"Available profiles: {', '.join(ids[:5])}" + ("..." if len(ids) > 5 else ""))
            else:
                print("No profiles exist yet. Try creating one:")
                print(f"  ➜ profile {entity_id} update --behavior amount:100")
            return

        profile = df[df['entity_id'] == target_id].iloc[0]
        
        # Create a figure
        fig = plt.Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        
        # Plot something meaningful - e.g., amounts if they exist in behavior
        try:
             profile_obj = self.tracker.profiles.get(target_id)
             if profile_obj and profile_obj.behavioral_signals:
                 amounts = [float(entry.get('amount', 0)) for entry in profile_obj.behavioral_signals if 'amount' in entry]
                 if amounts:
                     ax.plot(amounts, marker='o', linestyle='-', color='#7ee787')
                     ax.set_title(f"Transaction Amount History: {target_id}")
                     ax.set_xlabel("Event Index")
                     ax.set_ylabel("Amount")
                     print(f"✔ Visualizing timeline for {target_id}")
                     self.plot_callback(fig)
                     return
        except Exception as e:
            print(f"Debug: {e}")

        # Fallback plot if no data
        ax.text(0.5, 0.5, "No numeric timeline data available", 
                ha='center', va='center', transform=ax.transAxes)
        ax.set_title(f"Profile: {target_id}")
        self.plot_callback(fig)
        print("⚠ No numeric data to plot for this profile.")


    def handle_profile(self, args):
        if not args:
            super().handle_profile(args)
            return

        # Support "profile update <ID>" syntax (re-order args if needed)
        # Expected native: profile <ID> update ...
        # If user did: profile update <ID> ...
        if args[0].lower() == 'update' and len(args) > 1:
            # Swap update and ID
            # args was ['update', 'ID', ...] -> ['ID', 'update', ...]
            new_args = [args[1], args[0]] + args[2:]
            args = new_args
            
        entity_id = args[0]
        if len(args) == 1:
             # Showing a single profile
             profile = self.tracker.get_or_create_profile(entity_id)
             print(f"Loaded profile: {entity_id}")
             # Convert dict to df for table
             data = profile.to_dict()
             # Flatten slightly for display
             flat_data = []
             for k, v in data.items():
                 if isinstance(v, list):
                     flat_data.append({"Field": k, "Value": f"[{len(v)} items]"})
                 else:
                     flat_data.append({"Field": k, "Value": str(v)})
                     
             if not flat_data:
                 flat_data = [{"Field": "Status", "Value": "Empty Profile"}]
                 
             df = pd.DataFrame(flat_data)
             self.table_callback(df)
        else:
            super().handle_profile(args)

class ConsoleRedirector:
    def __init__(self, check_func, text_widget, tag_stdout, tag_stderr):
        self.text_widget = text_widget
        self.tag_stdout = tag_stdout
        self.tag_stderr = tag_stderr
        self.check_func = check_func

    def write(self, string):
        if not self.check_func(): return
        self.text_widget.after(0, self._write, string)

    def _write(self, string):
        try:
            self.text_widget.configure(state='normal')
            self.text_widget.insert('end', string, self.tag_stdout)
            self.text_widget.see('end')
            self.text_widget.configure(state='disabled')
        except:
            pass

    def flush(self):
        pass

class ProfileApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Profile System Terminal")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1a1b1e")

        # Fonts
        self.font_mono = font.Font(family="Consolas", size=10)
        self.font_ui = font.Font(family="Segoe UI", size=10)

        # Style
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Treeview", 
                        background="#21262d", 
                        fieldbackground="#21262d", 
                        foreground="#c9d1d9",
                        rowheight=25)
        style.configure("Treeview.Heading", 
                        background="#30363d", 
                        foreground="#c9d1d9",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[('selected', '#58a6ff')])
        
        # Tabs
        style.configure("TNotebook", background="#1a1b1e", borderwidth=0)
        style.configure("TNotebook.Tab", background="#30363d", foreground="#c9d1d9", padding=[10, 5])
        style.map("TNotebook.Tab", background=[('selected', '#1a1b1e')], foreground=[('selected', '#58a6ff')])

        self.setup_ui()
        
        self.is_alive = True
        self.system = GUIProfileSystem(self.update_table, self.update_plot)
        self.original_stdout = sys.stdout
        sys.stdout = ConsoleRedirector(lambda: self.is_alive, self.term_text, "stdout", "stderr")
        
        # Autocomplete data
        self.commands = ['profile', 'cluster', 'analyze', 'visualize', 'mode', 'hitl', 'help', 'exit']
        
        print("Profile System v1.0 Initialized.")
        print("Type 'help' for commands.")

    def setup_ui(self):
        main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#1a1b1e", sashwidth=4)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # LEFT PANE
        left_frame = tk.Frame(main_pane, bg="#1a1b1e")
        main_pane.add(left_frame, minsize=400, stretch="always")
        
        self.term_text = tk.Text(left_frame, bg="#0e1117", fg="#c9d1d9", 
                                 font=self.font_mono, insertbackground="white",
                                 relief=tk.FLAT, padx=10, pady=10, state='disabled')
        self.term_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.term_text.tag_config("stdout", foreground="#c9d1d9")
        self.term_text.tag_config("stderr", foreground="#ff7b72")
        
        # Autocomplete Popup (Hidden initially)
        self.suggestion_lb = tk.Listbox(self.root, bg="#30363d", fg="#c9d1d9", font=self.font_mono, relief=tk.FLAT)
        self.suggestion_lb.bind("<<ListboxSelect>>", self.use_suggestion)
        
        input_frame = tk.Frame(left_frame, bg="#1a1b1e")
        input_frame.pack(fill=tk.X)
        
        tk.Label(input_frame, text="➜", bg="#1a1b1e", fg="#58a6ff", font=("Consolas", 12, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        
        self.cmd_entry = tk.Entry(input_frame, bg="#0d1117", fg="#c9d1d9", 
                                  font=self.font_mono, insertbackground="white",
                                  relief=tk.FLAT, bd=1)
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.cmd_entry.config(highlightbackground="#30363d", highlightcolor="#58a6ff", highlightthickness=1)
        self.cmd_entry.bind("<Return>", self.on_enter)
        self.cmd_entry.bind("<KeyRelease>", self.check_autocomplete)
        self.cmd_entry.bind("<Up>", self.nav_suggestion)
        self.cmd_entry.bind("<Down>", self.nav_suggestion)
        self.cmd_entry.focus_set()

        # RIGHT PANE
        right_frame = tk.Frame(main_pane, bg="#21262d")
        main_pane.add(right_frame, minsize=400, stretch="always")
        
        # Info Header
        self.stats_frame = tk.Frame(right_frame, bg="#161b22", bd=1, relief=tk.SOLID)
        self.stats_frame.pack(fill=tk.X, padx=10, pady=10)
        self.lbl_profiles = tk.Label(self.stats_frame, text="Profiles: 0", bg="#161b22", fg="#c9d1d9", font=("Segoe UI", 10))
        self.lbl_profiles.pack(side=tk.LEFT, padx=10, pady=5)
        self.lbl_mode = tk.Label(self.stats_frame, text="Mode: ANALYSIS", bg="#161b22", fg="#7ee787", font=("Segoe UI", 10, "bold"))
        self.lbl_mode.pack(side=tk.RIGHT, padx=10, pady=5)

        # Tabs for Table vs Plot
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Table Tab
        self.table_frame = tk.Frame(self.notebook, bg="#21262d")
        self.notebook.add(self.table_frame, text=" 📄 Data View ")
        
        y_scroll = ttk.Scrollbar(self.table_frame, orient="vertical")
        x_scroll = ttk.Scrollbar(self.table_frame, orient="horizontal")
        self.tree = ttk.Treeview(self.table_frame, columns=(), show="headings", 
                                 yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.config(command=self.tree.yview)
        x_scroll.config(command=self.tree.xview)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Visualization Tab
        self.plot_frame = tk.Frame(self.notebook, bg="#21262d")
        self.notebook.add(self.plot_frame, text=" 📈 Visualization ")
        self.canvas = None

    def check_autocomplete(self, event):
        # Basic autocomplete logic
        if event.keysym in ['Up', 'Down', 'Return']: return
        
        typed = self.cmd_entry.get().split(' ')[-1] # Check last word
        if not typed:
            self.suggestion_lb.place_forget()
            return

        matching = [c for c in self.commands if c.startswith(typed)]
        if matching:
            self.suggestion_lb.delete(0, tk.END)
            for m in matching:
                self.suggestion_lb.insert(tk.END, m)
            
            # Position popup
            x = self.cmd_entry.winfo_rootx() - self.root.winfo_rootx() + (len(self.cmd_entry.get()) - len(typed)) * 8 # Approximate char width
            y = self.cmd_entry.winfo_rooty() - self.root.winfo_rooty() + 30
            self.suggestion_lb.place(x=x, y=y, width=150, height=100)
            self.suggestion_lb.selection_set(0)
        else:
            self.suggestion_lb.place_forget()

    def nav_suggestion(self, event):
        if not self.suggestion_lb.winfo_ismapped(): return
        cur_idx = self.suggestion_lb.curselection()
        if not cur_idx: cur_idx = (0,)
        
        if event.keysym == 'Up':
            new_idx = max(0, cur_idx[0] - 1)
        else:
            new_idx = min(self.suggestion_lb.size() - 1, cur_idx[0] + 1)
            
        self.suggestion_lb.selection_clear(0, tk.END)
        self.suggestion_lb.selection_set(new_idx)
        return "break"

    def use_suggestion(self, event):
        if not self.suggestion_lb.curselection(): return
        selected = self.suggestion_lb.get(self.suggestion_lb.curselection())
        
        full_text = self.cmd_entry.get()
        words = full_text.split(' ')
        words[-1] = selected
        new_text = ' '.join(words)
        
        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.insert(0, new_text)
        self.suggestion_lb.place_forget()
        self.cmd_entry.focus_set()

    def on_enter(self, event):
        if self.suggestion_lb.winfo_ismapped():
            self.use_suggestion(None)
            return

        cmd = self.cmd_entry.get()
        if not cmd: return
        self.cmd_entry.delete(0, 'end')
        self.suggestion_lb.place_forget()
        
        self.term_text.configure(state='normal')
        self.term_text.insert('end', f"\n➜ {cmd}\n", "stdout")
        self.term_text.see('end')
        self.term_text.configure(state='disabled')
        
        threading.Thread(target=self.run_command, args=(cmd,), daemon=True).start()

    def run_command(self, cmd):
        try:
            self.system.process_command(cmd)
            self.update_stats()
        except Exception as e:
            print(f"Error: {e}")

    def update_stats(self):
        self.root.after(0, self._update_stats_ui)

    def _update_stats_ui(self):
        count = len(self.system.tracker.profiles)
        self.lbl_profiles.config(text=f"Profiles: {count}")
        self.lbl_mode.config(text=f"Mode: {self.system.current_mode.upper()}")

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
            vals = [str(x) for x in row.tolist()]
            self.tree.insert("", "end", values=vals)

    def update_plot(self, fig):
        self.root.after(0, self._update_plot_ui, fig)
        
    def _update_plot_ui(self, fig):
        self.notebook.select(self.plot_frame)
        # Clear old canvas
        for widget in self.plot_frame.winfo_children():
            widget.destroy()
            
        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def on_close(self):
        self.is_alive = False
        sys.stdout = self.original_stdout
        self.root.destroy()
        os._exit(0) # Force kill threads

if __name__ == "__main__":
    root = tk.Tk()
    app = ProfileApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
