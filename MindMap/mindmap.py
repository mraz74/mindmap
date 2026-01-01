# (Full file contents)
import tkinter as tk
from tkinter import simpledialog, messagebox, Menu, filedialog, ttk, font as tkfont, colorchooser
import json
import os
import webbrowser
import re
import io
import tempfile
import datetime as dt

# Pillow is required for exporting to PNG/PDF from PostScript.
try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# Default node fill color
DEFAULT_NODE_COLOR = "#ffffff"

# --- TODO  ---
# --- Add copy paste of pictures (Saved as files in the DB folder)
# --- Add an option to add a excel table to resources
# --- Add todo list to project or resources. Add option to see all todo of all nodes
# --- Move delete button of Resources window to the left and add a close button in the right
# --- Add sort option of nodes children order by name
# --- Add Icon when Node has resources + Number of children inside the block
# --- when open a window do it in the same screen (in case of multiple PC screens)

# --- HIGH DPI FIX ---
try:
    from ctypes import windll

    windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


def iso_now():
    """Return current UTC time as ISO 8601 string (no timezone suffix)."""
    return dt.datetime.utcnow().replace(microsecond=0).isoformat()


def parse_iso(s):
    """Parse ISO 8601 produced by iso_now(); fall back to epoch if invalid."""
    if not s:
        return dt.datetime.fromtimestamp(0)
    if isinstance(s, (int, float)):
        return dt.datetime.utcfromtimestamp(s)
    try:
        # fromisoformat handles the format we create (YYYY-MM-DDTHH:MM:SS)
        return dt.datetime.fromisoformat(s)
    except Exception:
        try:
            # try a fallback parse
            return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return dt.datetime.fromtimestamp(0)


# --- NOTE DIALOG CLASS ---
class NoteDialog(tk.Toplevel):
    def __init__(self, parent, initial_data=None):
        super().__init__(parent)
        self.title("Note Editor")
        self.geometry("600x550")
        self.result = None

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.save_and_close)

        # Title Entry
        tk.Label(self, text="Title:", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=15, pady=(10, 0))
        self.title_var = tk.StringVar(value=initial_data.get("title", "New Note") if initial_data else "New Note")
        tk.Entry(self, textvariable=self.title_var, font=("Segoe UI", 10), relief="flat", bg="#f8f9fa").pack(
            fill="x", padx=15, pady=5
        )

        # Main Text Box
        tk.Label(
            self,
            text="Content (Ctrl+B: Bold | *: Bullet | 1.: Numbering | Links auto-detected):",
            font=("Segoe UI", 6, "italic"),
            fg="#7f8c8d",
        ).pack(anchor="w", padx=15)
        self.text_area = tk.Text(self, font=("Segoe UI", 6), undo=True, wrap="word", padx=10, pady=10)
        self.text_area.pack(fill="both", expand=True, padx=15, pady=5)

        # Tag Configuration
        self.text_area.tag_configure("bold", font=("Segoe UI", 6, "bold"))
        self.text_area.tag_configure("link", foreground="blue", underline=True)

        # Bindings
        self.text_area.tag_bind("link", "<Button-1>", self.open_link)
        self.text_area.tag_bind("link", "<Enter>", lambda e: self.text_area.config(cursor="hand2"))
        self.text_area.tag_bind("link", "<Leave>", lambda e: self.text_area.config(cursor=""))
        self.text_area.bind("<Control-b>", self.toggle_bold)
        self.text_area.bind("<KeyRelease-space>", self.handle_space)
        self.text_area.bind("<Return>", self.handle_enter)

        if initial_data:
            self.text_area.insert("1.0", initial_data.get("content", ""))
            self.scan_for_links()

        # Save Button
        tk.Button(
            self,
            text="Save Note",
            bg="#2ecc71",
            fg="white",
            font=("Segoe UI", 6, "bold"),
            command=self.save_and_close,
            relief="flat",
            pady=8,
        ).pack(pady=10)

    def toggle_bold(self, event=None):
        try:
            if self.text_area.tag_ranges("sel"):
                current_tags = self.text_area.tag_names("sel.first")
                if "bold" in current_tags:
                    self.text_area.tag_remove("bold", "sel.first", "sel.last")
                else:
                    self.text_area.tag_add("bold", "sel.first", "sel.last")
            return "break"
        except tk.TclError:
            pass

    def scan_for_links(self):
        self.text_area.tag_remove("link", "1.0", "end")
        content = self.text_area.get("1.0", "end")
        url_pattern = r"(https?://[^\s]+|www\.[^\s]+)"
        for match in re.finditer(url_pattern, content):
            self.text_area.tag_add("link", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

    def open_link(self, event):
        click_pos = self.text_area.index(f"@{event.x},{event.y}")
        if "link" in self.text_area.tag_names(click_pos):
            ranges = self.text_area.tag_prevrange("link", click_pos + "+1c")
            if ranges:
                url = self.text_area.get(*ranges)
                if url.startswith("www."):
                    url = "http://" + url
                webbrowser.open(url)

    def handle_space(self, event):
        cursor_idx = self.text_area.index("insert")
        line_start = self.text_area.index("insert linestart")
        line_content = self.text_area.get(line_start, cursor_idx)
        if line_content == "* ":
            self.text_area.delete(line_start, cursor_idx)
            self.text_area.insert(line_start, "• ")
        self.scan_for_links()

    def handle_enter(self, event):
        cursor_idx = self.text_area.index("insert")
        line_start = self.text_area.index("insert linestart")
        line_content = self.text_area.get(line_start, cursor_idx).strip()

        if line_content == "•":
            self.text_area.delete(line_start, cursor_idx)
            self.text_area.insert(line_start, "\n")
            self.scan_for_links()
            return "break"
        elif line_content.startswith("•"):
            self.text_area.insert("insert", "\n• ")
            self.scan_for_links()
            return "break"

        if ". " in line_content or (line_content.endswith(".") and line_content[:-1].isdigit()):
            parts = line_content.split(". ", 1)
            if parts[0].isdigit():
                num = int(parts[0])
                if len(line_content.replace(f"{num}.", "").strip()) == 0:
                    self.text_area.delete(line_start, cursor_idx)
                    self.text_area.insert(line_start, "\n")
                else:
                    self.text_area.insert("insert", f"\n{num + 1}. ")
                self.scan_for_links()
                return "break"

        self.text_area.insert("insert", "\n")
        self.scan_for_links()
        return "break"

    def save_and_close(self):
        self.result = {
            "type": "note",
            "title": self.title_var.get().strip() or "Untitled Note",
            "content": self.text_area.get("1.0", "end-1c"),
        }
        self.destroy()


# --- TOOLTIP CLASS ---
class NodeTooltip:
    def __init__(self, canvas):
        self.canvas = canvas
        self.tip_window = None

    def show(self, text, x, y):
        if self.tip_window or not text:
            return
        x += 20
        y += 20
        self.tip_window = tw = tk.Toplevel(self.canvas)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{int(x)}+{int(y)}")
        tw.attributes("-topmost", True)
        tk.Label(
            tw,
            text=text,
            justify="left",
            background="#2c3e50",
            foreground="white",
            relief="flat",
            borderwidth=1,
            font=("Segoe UI", 6),
            padx=8,
            pady=5,
        ).pack()

    def hide(self):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class MindMapApp:
    def __init__(self, root):
        self.root = root

        # --- STORAGE & SETTINGS ---
        self.projects_dir = os.path.abspath("projects")
        os.makedirs(self.projects_dir, exist_ok=True)
        self.settings_path = os.path.join(self.projects_dir, "settings.json")

        self.settings = self.load_settings()
        self.current_project = self.settings.get("last_project", "central.json")

        self.root.geometry("1400x900")
        self.update_title()

        # --- FONT / VIEW STATE ---
        self.base_font_size = 6  # logical node font size
        # Search state
        self.search_matches = []  # list of (node_id, source_type)
        self.current_match_index = -1
        self.last_search_query = ""
        self._last_match_source = None

        # --- MENUS ---
        self.menu_bar = Menu(self.root)
        self.root.config(menu=self.menu_bar)
        self.file_menu = Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="New Project", command=self.new_project)
        self.file_menu.add_command(label="Open Project", command=self.open_project)
        self.recent_menu = Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label="Recent Projects", menu=self.recent_menu)
        self.update_recent_menu()
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Save As...", command=self.save_as_project)

        # --- EXPORT OPTIONS ---
        self.file_menu.add_command(label="Export as PNG...", command=self.export_as_png)
        self.file_menu.add_command(label="Export as PDF...", command=self.export_as_pdf)

        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.root.quit)

        # --- TOP TOOLBAR ---
        self.toolbar = tk.Frame(self.root, bg="#f5f5f7")
        self.toolbar.pack(fill="x", side="top")

        # Left side buttons
        tk.Button(
            self.toolbar,
            text="Reorganize",
            command=self.reorganize_and_zoom,
            bg="#c8e6c9",
            font=("Segoe UI", 6),
        ).pack(side="left", padx=5, pady=3)
        tk.Button(
            self.toolbar, text="Zoom All", command=self.zoom_all, bg="#d1d8ff", font=("Segoe UI", 6)
        ).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Expand All",   font=("Segoe UI", 6), command=self.expand_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Collapse All", font=("Segoe UI", 6), command=self.collapse_all).pack(side="left", padx=5, pady=3)

        # --- Search Bar (with navigation) ---
        search_frame = tk.Frame(self.toolbar, bg="#f5f5f7")
        search_frame.pack(side="left", padx=20)
        tk.Label(search_frame, text="Search:", font=("Segoe UI", 6), bg="#f5f5f7").pack(side="left")

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=25)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<Return>", self.perform_search)

        tk.Button(
            search_frame, text="Go", font=("Segoe UI", 6), command=lambda: self.perform_search(None), bg="#ffeaa7"
        ).pack(side="left")
        tk.Button(search_frame, text="Prev", font=("Segoe UI", 6), command=self.prev_match, bg="#dfe6e9").pack(side="left", padx=3)
        tk.Button(search_frame, text="Next", font=("Segoe UI", 6), command=self.next_match, bg="#dfe6e9").pack(side="left", padx=3)

        self.search_res_label = tk.Label(
            search_frame, text="", bg="#f5f5f7", font=("Segoe UI", 6, "bold"), fg="#555"
        )
        self.search_res_label.pack(side="left", padx=10)

        # --- Sort control ---
        sort_frame = tk.Frame(self.toolbar, bg="#f5f5f7")
        sort_frame.pack(side="left", padx=10)
        tk.Label(sort_frame, text="Sort:", font=("Segoe UI", 6), bg="#f5f5f7").pack(side="left")
        sort_options = ["None", "Name ↑", "Name ↓", "Date ↑", "Date ↓"]
        self.sort_var = tk.StringVar(value=self.settings.get("auto_sort", "None"))
        self.sort_menu = tk.OptionMenu(sort_frame, self.sort_var, *sort_options, command=self.set_sort_mode)
        self.sort_menu.config(font=("Segoe UI", 6))
        self.sort_menu.pack(side="left", padx=(6, 0))

        # Right side help
        tk.Button(self.toolbar, text="Help", font=("Segoe UI", 6), command=self.show_help).pack(side="right", padx=10, pady=3)

        # --- RIGHT VERTICAL TOOLBAR (icons for order) ---
        # This holds move up/down and will be visible on the right side of the window (vertical)
        self.right_toolbar = tk.Frame(self.root, bg="#f5f5f7", relief="flat")
        self.right_toolbar.pack(side="right", fill="y", padx=(0,6), pady=6)

        # Use Unicode arrows as icons
        self.icon_up = tk.Button(self.right_toolbar, text="▲", font=("Segoe UI", 14), width=3, command=self.move_selected_up)
        self.icon_up.pack(pady=(10, 6))
        self.icon_down = tk.Button(self.right_toolbar, text="▼", font=("Segoe UI", 14), width=3, command=self.move_selected_down)
        self.icon_down.pack(pady=(0, 10))

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            self.root, textvariable=self.status_var, bd=1, relief="sunken", anchor="w", bg="#f0f0f0"
        ).pack(side="bottom", fill="x")

        # --- CANVAS ---
        self.canvas = tk.Canvas(self.root, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.zoom_level = 1.0
        self.offset_x, self.offset_y = 700, 450
        self.pan_last_x, self.pan_last_y = 0, 0
        self.nodes = {}
        self.root_id = "root"
        self.selected = None
        self.dragging = None
        self.drag_box_start = None
        self.drop_target = None

        self.tooltip = NodeTooltip(self.canvas)
        self.hover_after_id = None
        self.last_hover_node = None

        # Bindings
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.do_pan)
        self.canvas.bind("<MouseWheel>", self.on_mouse_zoom)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        # Font size shortcuts (Ctrl + / Ctrl -)
        self.root.bind_all("<Control-plus>", self.increase_font)
        self.root.bind_all("<Control-minus>", self.decrease_font)
        # Some keyboards send <Control-equal> for Ctrl+ on main keyboard
        self.root.bind_all("<Control-equal>", self.increase_font)

        self.load_project()
        self.update_toolbar_buttons()
        self.root.after(500, self.reorganize_and_zoom)

    # --- FONT SIZE CONTROL ---
    def increase_font(self, event=None):
        self.base_font_size = min(self.base_font_size + 1, 36)
        # self.redraw()
        self.reorganize_and_zoom()
        return "break"

    def decrease_font(self, event=None):
        self.base_font_size = max(self.base_font_size - 1, 6)
        # self.redraw()
        self.reorganize_and_zoom()
        return "break"

    # --- SORTING & MANUAL ORDER PERSISTENCE ---
    def save_manual_orders(self):
        """Store current children order into 'manual_children' for each node."""
        for nid, node in self.nodes.items():
            if "children" in node:
                node["manual_children"] = list(node["children"])

    def restore_manual_orders(self):
        """Restore children order from 'manual_children' when available."""
        for nid, node in self.nodes.items():
            manual = node.get("manual_children")
            if manual:
                # Keep only children that still exist, preserve any new children appended at end
                restored = [c for c in manual if c in node.get("children", []) and c in self.nodes]
                # append any current children that were not present in manual list
                for c in node.get("children", []):
                    if c not in restored:
                        restored.append(c)
                node["children"] = restored

    def set_sort_mode(self, mode):
        """
        When switching modes:
          - If leaving 'None', save the manual order so we can restore it later.
          - If switching to 'None', restore previously saved manual order (if present).
          - If switching to a sort mode, apply sorting.
        """
        old = self.settings.get("auto_sort", "None")
        # if we're going from None -> non-None, save manual orders
        if old == "None" and mode != "None":
            self.save_manual_orders()
        # if going to None, restore previously-saved manual order (if any)
        if mode == "None":
            self.restore_manual_orders()
        self.settings["auto_sort"] = mode
        self.save_settings()
        if mode != "None":
            self.apply_sorting()
        self.update_toolbar_buttons()
        self.reorganize_and_zoom()

    def apply_sorting(self):
        """
        Sort every node's children in-place according to the selected sort mode.
        Modes: None, Name ↑, Name ↓, Date ↑, Date ↓
        Date sorting uses node['modified'] (ISO string). Missing modified treated as epoch.
        """
        mode = self.settings.get("auto_sort", "None")
        for nid, node in self.nodes.items():
            children = node.get("children", [])
            if not children:
                continue
            if mode == "None":
                continue
            if mode.startswith("Name"):
                reverse = mode.endswith("↓")
                try:
                    children.sort(key=lambda c: self.nodes.get(c, {}).get("text", "").lower(), reverse=reverse)
                except Exception:
                    pass
            elif mode.startswith("Date"):
                reverse = mode.endswith("↓")
                try:
                    children.sort(key=lambda c: parse_iso(self.nodes.get(c, {}).get("modified")), reverse=reverse)
                except Exception:
                    pass

    # --- SEARCH FUNCTIONALITY ---
    def perform_search(self, event):
        query = self.search_var.get().lower().strip()
        if not query:
            self.status_var.set("Please enter text to search.")
            self.search_res_label.config(text="")
            return

        # If query changed, recompute matches
        if query != self.last_search_query:
            if self.selected:
                self.selected = None
                self.redraw()

            self.last_search_query = query
            self.search_matches = []
            self.current_match_index = -1

            for nid, node in self.nodes.items():
                match = False
                self._last_match_source = None

                # Title
                if query in node["text"].lower():
                    match = True
                    self._last_match_source = "title"

                # Resources / notes
                if not match:
                    for link in node.get("links", []):
                        if isinstance(link, dict) and link.get("type") == "note":
                            if query in link.get("title", "").lower():
                                match = True
                                self._last_match_source = "note-title"
                                break
                            if query in link.get("content", "").lower():
                                match = True
                                self._last_match_source = "note-content"
                                break
                        else:
                            if query in str(link).lower():
                                match = True
                                self._last_match_source = "resource"
                                break

                if match:
                    source = self._last_match_source or "title"
                    self.search_matches.append((nid, source))

        # No matches
        if not self.search_matches:
            self.status_var.set(f"No matches found for '{query}'")
            self.search_res_label.config(text="0 found", fg="red")
            return

        # Move to next match (Go/Enter acts as 'Next')
        self.current_match_index = (self.current_match_index + 1) % len(self.search_matches)
        self._show_current_match()

    def next_match(self):
        if not self.search_matches:
            # Try running search if nothing yet
            self.perform_search(None)
            return
        self.current_match_index = (self.current_match_index + 1) % len(self.search_matches)
        self._show_current_match()

    def prev_match(self):
        if not self.search_matches:
            self.perform_search(None)
            return
        self.current_match_index = (self.current_match_index - 1) % len(self.search_matches)
        self._show_current_match()

    def _show_current_match(self):
        if not self.search_matches:
            self.status_var.set("No matches to display.")
            self.search_res_label.config(text="0 found", fg="red")
            return

        nid, source = self.search_matches[self.current_match_index]
        self.reveal_node(nid)
        self.center_on_node(nid)
        self.selected = nid

        count_text = f"{self.current_match_index + 1} of {len(self.search_matches)}"
        source_names = {
            "title": "Title",
            "note-title": "Note title",
            "note-content": "Note body",
            "resource": "Resource",
        }
        src_text = source_names.get(source, "Match")
        self.search_res_label.config(text=count_text, fg="#2ecc71")
        self.status_var.set(f"Match {count_text} ({src_text}): {self.nodes[nid]['text']}")
        self.redraw()
        self.update_toolbar_buttons()

    def reveal_node(self, nid):
        current = nid
        child_to_parent = {}
        for pid, node in self.nodes.items():
            for child in node["children"]:
                child_to_parent[child] = pid

        while current in child_to_parent:
            parent_id = child_to_parent[current]
            self.nodes[parent_id]["expanded"] = True
            current = parent_id

        self.reorganize_nodes()

    def center_on_node(self, nid):
        if nid not in self.nodes:
            return
        nx, ny = self.nodes[nid]["pos"]
        sw = self.canvas.winfo_width()
        sh = self.canvas.winfo_height()
        self.offset_x = (sw / 2) - (nx * self.zoom_level)
        self.offset_y = (sh / 2) - (ny * self.zoom_level)
        self.redraw()

    # --- STANDARD APP LOGIC ---

    def on_mouse_move(self, e):
        nid = self.find_node_at(e.x, e.y, exclude=self.dragging)
        if nid != self.last_hover_node:
            self.cancel_hover()
            self.tooltip.hide()
            self.last_hover_node = nid
            if nid and not self.dragging:
                self.hover_after_id = self.root.after(
                    750, lambda: self.show_node_details(nid, e.x_root, e.y_root)
                )

    def cancel_hover(self):
        if self.hover_after_id:
            self.root.after_cancel(self.hover_after_id)
            self.hover_after_id = None

    def show_node_details(self, nid, root_x, root_y):
        node = self.nodes[nid]
        details = [f"Node: {node['text']}", f"Children: {len(node.get('children', []))}"]
        links = node.get("links", [])
        if links:
            details.append("\nResources:")
            for l in links[:5]:
                name = l["title"] if isinstance(l, dict) else os.path.basename(str(l))
                details.append(f"• {name}")
        # Show modified date if present
        mod = node.get("modified")
        if mod:
            details.append(f"\nModified: {mod}")
        self.tooltip.show("\n".join(details), root_x, root_y)

    def reorganize_nodes(self):
        if not self.nodes:
            return

        # Dynamic gaps based on font/zoom/node size
        f_size = max(10, self.base_font_size * self.zoom_level * 1.2)  # Scale preview
        scale_factor = f_size / 10  # Normalize to base 10pt
        v_gap = max(100, 80 * scale_factor)  # Min 100px vert
        h_gap = max(350, 260 * scale_factor)  # Min 350px horiz

        self.next_y = 0

        def layout_recursive(nid, depth):
            node = self.nodes[nid]
            x_pos = depth * h_gap

            # Estimate node height for better vert spacing
            node_font = tkfont.Font(family="Segoe UI", size=int(f_size), weight="bold")
            tw = node_font.measure(node["text"])
            margin = 25 * self.zoom_level
            px = max(75 * self.zoom_level, (tw / 2) + margin)
            py = max(25 * self.zoom_level, f_size * 1.1)  # Taller py estimate
            node_height = py * 2 * 1.4  # Buffer for icons/selection

            if not node.get("expanded", True) or not node["children"]:
                y_pos = self.next_y
                node["pos"] = [x_pos, y_pos]
                self.next_y += node_height + v_gap * 0.3  # Smaller for leaves
                return y_pos

            child_ys = [layout_recursive(cid, depth + 1) for cid in node["children"] if cid in self.nodes]
            actual_y = (min(child_ys) + max(child_ys)) / 2 if child_ys else self.next_y
            node["pos"] = [x_pos, actual_y]

            # Extra vert buffer if children tight
            child_span = max(child_ys) - min(child_ys) if child_ys else 0
            if child_span < node_height * 1.5:
                self.next_y += v_gap * 0.2  # Nudge down

            return actual_y

        layout_recursive(self.root_id, 0)
        self.save_project()

    def reorganize_and_zoom(self):
        self.reorganize_nodes()
        self.zoom_all()

    def on_left_click(self, e):
        self.tooltip.hide()
        wx, wy = self.to_world(e.x, e.y)
        clicked_node = self.find_node_at(e.x, e.y)
        if clicked_node:
            nx, ny = self.nodes[clicked_node]["pos"]

            # Measure box width for dynamic hit detection on the "+" button
            f_size = max(5, int(self.base_font_size * self.zoom_level))
            node_font = tkfont.Font(family="Segoe UI", size=f_size, weight="bold")
            tw = node_font.measure(self.nodes[clicked_node]["text"])
            margin = 25 * self.zoom_level
            px = (tw / 2) + margin
            px = max(75 * self.zoom_level, px) / self.zoom_level

            if (nx + px - 15) < wx < (nx + px + 15) and (ny - 15) < wy < (ny + 15):
                self.selected = clicked_node
                self.add_branch()
                return
            self.selected = clicked_node
            self.dragging = self.selected
        else:
            self.drag_box_start = (e.x, e.y)
        self.redraw()
        self.update_toolbar_buttons()

    def is_descendant(self, parent_id, child_id):
        if child_id in self.nodes[parent_id]["children"]:
            return True
        for sub_child in self.nodes[parent_id]["children"]:
            if self.is_descendant(sub_child, child_id):
                return True
        return False

    def on_drag(self, e):
        self.cancel_hover()
        self.tooltip.hide()
        if self.dragging:
            self.nodes[self.dragging]["pos"] = self.to_world(e.x, e.y)
            target = self.find_node_at(e.x, e.y, exclude=self.dragging)
            if target and target != self.dragging and not self.is_descendant(self.dragging, target):
                self.drop_target = target
            else:
                self.drop_target = None
            self.redraw()
        elif self.drag_box_start:
            self.redraw()
            x0, y0 = self.drag_box_start
            color = "#3498db" if (e.x > x0 and e.y > y0) else "#2ecc71"
            self.canvas.create_rectangle(x0, y0, e.x, e.y, outline=color, dash=(4, 4), width=2)

    def on_release(self, e):
        if self.dragging:
            if self.drop_target and self.dragging != self.root_id:
                # detach from old parent
                for pid, node in self.nodes.items():
                    if self.dragging in node["children"]:
                        node["children"].remove(self.dragging)
                        node["modified"] = iso_now()
                        # keep manual order updated
                        if "manual_children" in node:
                            node["manual_children"] = [c for c in node["children"]]
                        break
                # attach to new parent
                self.nodes[self.drop_target]["children"].append(self.dragging)
                self.nodes[self.drop_target]["modified"] = iso_now()
                if self.settings.get("auto_sort", "None") == "None":
                    # In manual mode, update manual_children to reflect new order
                    self.nodes[self.drop_target]["manual_children"] = list(self.nodes[self.drop_target]["children"])
                else:
                    # In sorted mode, apply sorting after reparent
                    self.apply_sorting()
                self.reorganize_and_zoom()
            else:
                self.reorganize_nodes()

            self.save_project()
            self.dragging = None
            self.drop_target = None
            self.redraw()
            self.update_toolbar_buttons()
        if self.drag_box_start:
            x0, y0 = self.drag_box_start
            if e.x < x0 or e.y < y0:
                if abs(e.x - x0) > 10:
                    self.zoom_all()
            elif abs(e.x - x0) > 10 and abs(e.y - y0) > 10:
                self.box_zoom(x0, y0, e.x, e.y)
            self.drag_box_start = None
            self.redraw()

    def box_zoom(self, x0, y0, x1, y1):
        wx0, wy0 = self.to_world(x0, y0)
        wx1, wy1 = self.to_world(x1, y1)
        ww, wh = (wx1 - wx0), (wy1 - wy0)
        sw, sh = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.zoom_level = min(sw / max(ww, 1), sh / max(wh, 1))
        self.offset_x = (sw / 2) - ((wx0 + wx1) / 2) * self.zoom_level
        self.offset_y = (sh / 2) - ((wy0 + wy1) / 2) * self.zoom_level
        self.redraw()

    def on_mouse_zoom(self, e):
        self.tooltip.hide()
        factor = 1.1 if e.delta > 0 else 0.9
        mx, my = self.to_world(e.x, e.y)
        self.zoom_level *= factor
        self.zoom_level = max(0.1, min(self.zoom_level, 5.0))
        self.offset_x = e.x - mx * self.zoom_level
        self.offset_y = e.y - my * self.zoom_level
        self.redraw()

    def do_pan(self, e):
        self.tooltip.hide()
        self.offset_x += e.x - self.pan_last_x
        self.offset_y += e.y - self.pan_last_y
        self.pan_last_x, self.pan_last_y = e.x, e.y
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        f_size = max(5, int(self.base_font_size * self.zoom_level))
        node_font = tkfont.Font(family="Segoe UI", size=f_size, weight="bold")

        # Calculate actual font height
        font_height = node_font.metrics("linespace")

        def draw_tree(nid, depth=0):
            node = self.nodes[nid]
            sx, sy = self.to_screen(*node["pos"])

            tw = node_font.measure(node["text"])
            margin_x = 25 * self.zoom_level
            # Use font_height for vertical padding instead of just f_size
            margin_y = 10 * self.zoom_level

            px = max(75 * self.zoom_level, (tw / 2) + margin_x)
            py = (font_height / 2) + margin_y

            if node.get("expanded", True):
                for cid in node["children"]:
                    if cid in self.nodes:
                        cx, cy = self.to_screen(*self.nodes[cid]["pos"])
                        self.canvas.create_line(
                            sx,
                            sy,
                            (sx + cx) / 2,
                            sy,
                            (sx + cx) / 2,
                            cy,
                            cx,
                            cy,
                            smooth=True,
                            fill="#dcdde1",
                            width=max(1, int(2 * self.zoom_level)),
                        )
                        draw_tree(cid, depth + 1)

            color = ["#4834d4", "#686de0", "#eb4d4b", "#6ab04c"][depth % 4]
            bw = 4 if nid == self.drop_target else max(1, int(2 * self.zoom_level))
            dash = (5, 5) if nid == self.drop_target else None

            # Node fill color (per-node)
            node_color = node.get("color", DEFAULT_NODE_COLOR)
            # Choose a readable text color (black/white) based on fill luminance
            text_color = self._choose_text_color(node_color)

            if nid == self.selected:
                self.canvas.create_oval(
                    sx - px - 5,
                    sy - py - 5,
                    sx + px + 5,
                    sy + py + 5,
                    outline="#f1c40f",
                    width=3,
                )

            self.canvas.create_rectangle(
                sx - px, sy - py, sx + px, sy + py, fill=node_color, outline=color, width=bw, dash=dash
            )
            self.canvas.create_text(
                sx,
                sy,
                text=node["text"],
                font=node_font,
                fill=text_color,
            )
            br = 8 * self.zoom_level
            self.canvas.create_oval(
                sx + px - br, sy - br, sx + px + br, sy + br, fill="white", outline=color
            )
            self.canvas.create_text(
                sx + px,
                sy,
                text="+",
                fill=color,
                font=("Segoe UI", max(6, int(9 * self.zoom_level)), "bold"),
            )
            if not node.get("expanded", True) and node["children"]:
                self.canvas.create_text(
                    sx + px - 12,
                    sy + py - 8,
                    text=f"({len(node['children'])})",
                    font=("Segoe UI", max(5, int(7 * self.zoom_level))),
                    fill="#636e72",
                )
            if node.get("links"):
                # Fixed: Scale position and font fully with zoom and base_font_size
                icon_size = max(8, int(self.base_font_size * 0.8 * self.zoom_level))
                icon_pad = 12 * self.zoom_level  # Scaled padding from box edge
                self.canvas.create_text(
                    sx - px + icon_pad,
                    sy - py + icon_pad,
                    text="🔗",
                    font=("Segoe UI", icon_size, "bold"),
                    fill=color,
                    anchor="center"  # Ensures proper centering at scaled pos
                )

        if self.nodes:
            draw_tree(self.root_id)

    def _choose_text_color(self, hex_color):
        """
        Return 'black' or 'white' depending on luminance for readability.
        """
        try:
            h = hex_color.lstrip("#")
            if len(h) == 3:
                # shorthand e.g. "abc" => "aabbcc"
                h = "".join([c * 2 for c in h])
            r = int(h[0:2], 16)
            g = int(h[2:4], 16)
            b = int(h[4:6], 16)
        except Exception:
            return "black"
        # perceived luminance formula
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return "black" if lum > 160 else "white"

    def to_screen(self, wx, wy):
        return (wx * self.zoom_level) + self.offset_x, (wy * self.zoom_level) + self.offset_y

    def to_world(self, sx, sy):
        return (sx - self.offset_x) / self.zoom_level, (sy - self.offset_y) / self.zoom_level

    def zoom_all(self):
        if not self.nodes:
            return
        v = []

        def col(nid):
            v.append(self.nodes[nid]["pos"])
            if self.nodes[nid].get("expanded", True):
                for cid in self.nodes[nid]["children"]:
                    col(cid)

        col(self.root_id)
        if not v:
            return
        ax = [p[0] for p in v]
        ay = [p[1] for p in v]
        min_wx, max_wx, min_wy, max_wy = min(ax) - 150, max(ax) + 150, min(ay) - 100, max(ay) + 100
        sw, sh = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        self.zoom_level = min(sw / max(max_wx - min_wx, 1), sh / max(max_wy - min_wy, 1), 1.5)
        self.offset_x = (sw / 2) - ((min_wx + max_wx) / 2) * self.zoom_level
        self.offset_y = (sh / 2) - ((min_wy + max_wy) / 2) * self.zoom_level
        self.redraw()

    def show_help(self):
        h = (
            "Mind Map Pro - Quick Reference\n\n"
            "🖱️ NAVIGATION\n"
            "- Pan: Right-click and drag the background to move.\n"
            "- Zoom: Use the Mouse Wheel to zoom in/out.\n"
            "- Box Zoom: Left-click and drag a box to zoom into an area.\n"
            "- Reset View: Drag a box backwards (bottom-right to top-left) or click 'Zoom All'.\n\n"
            "🌿 NODES & STRUCTURE\n"
            "- Add Branch: Click the (+) icon on a node or use Right-click > Add Branch.\n"
            "- Reparent: Drag a node and drop it onto another to change its parent.\n"
            "- Expand/Collapse: Double-click a node with children to toggle visibility.\n"
            "- Edit Text: Double-click a node (without resources) or use Right-click > Edit.\n"
            "- Set Color: Right-click a node and choose 'Set Color...' to change its fill color.\n"
            "- Manual ordering: When Sort is 'None' you can use the Up/Down icons on the right toolbar\n"
            "  to change a node's order among its siblings. These are disabled when a sort mode is active.\n\n"
            "🔍 SEARCH\n"
            "- Deep Search: Type in the search bar to find text in Titles, Resource paths, or Note content.\n"
            "- Navigation: Use 'Prev' and 'Next' to cycle through matching nodes.\n\n"
            "📝 RESOURCES & NOTES\n"
            "- Manage: Right-click > Resources or double-click a node with a 🔗 icon.\n"
            "- Note Formatting: Inside notes, use Ctrl+B (Bold), '*' (Bullet), or '1.' (Numbered).\n\n"
            "🔤 FONT\n"
            "- Increase node font: Ctrl +\n"
            "- Decrease node font: Ctrl -\n\n"
            "🖨️ EXPORT\n"
            "- Export as PNG or PDF via File > Export as PNG... / Export as PDF...\n"
            "- Requires Pillow and Ghostscript (for PostScript conversion) to be installed."
        )
        messagebox.showinfo("Help", h)

    def load_settings(self):
        if os.path.exists(self.settings_path):
            with open(self.settings_path, "r") as f:
                try:
                    return json.load(f)
                except Exception:
                    return {"last_project": "central.json", "recent": [], "auto_sort": "None"}
        return {"last_project": "central.json", "recent": [], "auto_sort": "None"}

    def save_settings(self):
        with open(self.settings_path, "w") as f:
            json.dump(self.settings, f, indent=2)

    def update_recent_list(self, filename):
        r = self.settings.get("recent", [])
        if filename in r:
            r.remove(filename)
        r.insert(0, filename)
        self.settings["recent"], self.settings["last_project"] = r[:5], filename
        self.save_settings()
        self.update_recent_menu()

    def update_recent_menu(self):
        self.recent_menu.delete(0, "end")
        for f in self.settings.get("recent", []):
            # capture f to avoid late-binding in lambda
            self.recent_menu.add_command(label=f, command=lambda fn=f: self.switch_project(fn))

    def switch_project(self, filename):
        self.current_project = filename
        self.load_project()
        self.update_title()
        self.update_recent_list(filename)
        self.reorganize_and_zoom()

    def new_project(self):
        name = simpledialog.askstring("New", "Project Name:")
        if name:
            if not name.endswith(".json"):
                name += ".json"
            self.current_project = name
            now = iso_now()
            self.nodes = {
                self.root_id: {
                    "text": "Central Idea",
                    "children": [],
                    "pos": (0, 0),
                    "expanded": True,
                    "links": [],
                    "color": DEFAULT_NODE_COLOR,
                    "modified": now,
                    "manual_children": [],
                }
            }
            self.save_project()
            self.update_recent_list(name)
            self.update_title()
            self.apply_sorting()
            self.reorganize_and_zoom()

    def open_project(self):
        path = filedialog.askopenfilename(initialdir=self.projects_dir, filetypes=[("JSON", "*.json")])
        if path:
            self.switch_project(os.path.basename(path))

    def save_as_project(self):
        path = filedialog.asksaveasfilename(initialdir=self.projects_dir, defaultextension=".json")
        if path:
            self.current_project = os.path.basename(path)
            self.save_project()
            self.update_recent_list(self.current_project)
            self.update_title()

    def update_title(self):
        self.root.title(f"Mind Map Pro - [{self.current_project}]")

    def save_project(self):
        # Save nodes with ISO timestamps and manual_children if present
        with open(os.path.join(self.projects_dir, self.current_project), "w") as f:
            json.dump(self.nodes, f, indent=2)

    def load_project(self):
        p = os.path.join(self.projects_dir, self.current_project)
        if os.path.exists(p):
            with open(p, "r") as f:
                self.nodes = json.load(f)
            for n in self.nodes.values():
                n.setdefault("links", [])
                n.setdefault("color", DEFAULT_NODE_COLOR)
                # Normalize modified to ISO string if numeric; otherwise ensure it's present
                mod = n.get("modified")
                if isinstance(mod, (int, float)):
                    n["modified"] = dt.datetime.utcfromtimestamp(mod).replace(microsecond=0).isoformat()
                elif not mod:
                    n["modified"] = dt.datetime.fromtimestamp(0).replace(microsecond=0).isoformat()
                # ensure manual_children is present (use children as default)
                if "manual_children" not in n:
                    n["manual_children"] = list(n.get("children", []))
            # Apply any stored sort preference
            if self.settings.get("auto_sort", "None") != "None":
                self.apply_sorting()
        else:
            now = iso_now()
            self.nodes = {
                self.root_id: {
                    "text": "Central Idea",
                    "children": [],
                    "pos": (0, 0),
                    "expanded": True,
                    "links": [],
                    "color": DEFAULT_NODE_COLOR,
                    "modified": now,
                    "manual_children": [],
                }
            }

    def find_node_at(self, x, y, exclude=None):
        wx, wy = self.to_world(x, y)
        f_size = max(5, int(self.base_font_size * self.zoom_level))
        node_font = tkfont.Font(family="Segoe UI", size=f_size, weight="bold")
        font_height = node_font.metrics("linespace")

        for nid, node in self.nodes.items():
            if nid == exclude:
                continue
            nx, ny = node["pos"]

            tw = node_font.measure(node["text"])
            margin_x = 25 * self.zoom_level
            margin_y = 10 * self.zoom_level

            # Convert screen-space dimensions back to world-space for comparison
            px = max(75 * self.zoom_level, (tw / 2) + margin_x) / self.zoom_level
            py = ((font_height / 2) + margin_y) / self.zoom_level

            if nx - px < wx < nx + px and ny - py < wy < ny + py:
                return nid
        return None

    def on_right_press(self, e):
        self.tooltip.hide()
        self.pan_last_x, self.pan_last_y = e.x, e.y
        self.show_right_click_menu(e)

    def show_right_click_menu(self, event):
        self.selected = self.find_node_at(event.x, event.y)
        menu = Menu(self.root, tearoff=0)
        if self.selected:
            menu.add_command(label="Resources...", command=lambda: self.manage_resources(self.selected))
            menu.add_command(label="Edit Text", command=lambda: self.edit_node_text(self.selected))
            menu.add_command(label="Add Branch", command=self.add_branch)
            menu.add_command(label="Set Color...", command=lambda nid=self.selected: self.set_node_color(nid))
            menu.add_command(label="Clear Color", command=lambda nid=self.selected: self.clear_node_color(nid))
            menu.add_command(label="Delete", command=self.delete_node, foreground="red")
        else:
            menu.add_command(label="Reorganize & Zoom", command=self.reorganize_and_zoom)
        menu.post(event.x_root, event.y_root)
        self.update_toolbar_buttons()

    def on_double_click(self, e):
        self.tooltip.hide()
        nid = self.find_node_at(e.x, e.y)
        if nid:
            if self.nodes[nid].get("links"):
                self.manage_resources(nid)
            elif self.nodes[nid]["children"]:
                self.nodes[nid]["expanded"] = not self.nodes[nid].get("expanded", True)
                self.reorganize_and_zoom()
            else:
                self.edit_node_text(nid)

    def manage_resources(self, nid):
        node = self.nodes[nid]

        manager = tk.Toplevel(self.root)
        manager.title(f"Resources: {node['text']}")
        manager.geometry("720x520")
        manager.minsize(660, 440)
        manager.transient(self.root)
        manager.grab_set()

        # ---- CRITICAL WINDOWS DPI FIX ----
        style = ttk.Style(manager)
        try:
            style.theme_use("vista")   # forces correct header metrics on Windows
        except tk.TclError:
            pass

        style.configure(
            "Treeview",
            rowheight=30,
            font=("Segoe UI", 6)
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 6, "bold"),
            padding=(10, 6)
        )

        manager.columnconfigure(0, weight=1)
        manager.rowconfigure(0, weight=1)
        manager.rowconfigure(1, weight=0)

        frame = tk.Frame(manager)
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        tree = ttk.Treeview(
            frame,
            columns=("Type", "Path"),
            show="headings",
            selectmode="browse"
        )

        tree.heading("Type", text="Type")
        tree.heading("Path", text="Path / URL / Title")

        tree.column("Type", width=130, anchor="w", stretch=False)
        tree.column("Path", width=520, anchor="w", stretch=True)

        tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

        btn_frame = tk.Frame(manager)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 12))

        def refresh():
            tree.delete(*tree.get_children())
            for idx, l in enumerate(node.get("links", [])):
                if isinstance(l, dict) and l.get("type") == "note":
                    tree.insert("", "end", iid=str(idx),
                                values=("📝 Note", l.get("title", "Untitled")))
                else:
                    rtype = "🌐 Web" if str(l).startswith("http") else "📄 File"
                    tree.insert("", "end", iid=str(idx), values=(rtype, l))

        def open_selected(event=None):
            sel = tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            item = node["links"][idx]

            if isinstance(item, dict) and item.get("type") == "note":
                dlg = NoteDialog(manager, initial_data=item)
                manager.wait_window(dlg)
                if dlg.result:
                    node["links"][idx] = dlg.result
                    node["modified"] = iso_now()
                    self.save_project()
                    refresh()
            else:
                webbrowser.open(item)

        tree.bind("<Double-1>", open_selected)

        tk.Button(
            btn_frame,
            text="+ URL",
            font=("Segoe UI", 6),
            command=lambda: add_url(),
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame,
            text="+ File",
            font=("Segoe UI", 6),
            command=lambda: add_file(),
        ).pack(side="left", padx=4)

        def add_url():
            u = simpledialog.askstring("URL", "Address:")
            if u:
                node["links"].append(u)
                node["modified"] = iso_now()
                refresh()
                self.save_project()
                self.redraw()

        def add_file():
            f = filedialog.askopenfilename()
            if f:
                node["links"].append(f)
                node["modified"] = iso_now()
                refresh()
                self.save_project()
                self.redraw()

        def add_note():
            dlg = NoteDialog(manager)
            manager.wait_window(dlg)
            if dlg.result:
                node["links"].append(dlg.result)
                node["modified"] = iso_now()
                refresh()
                self.save_project()
                self.redraw()

        tk.Button(btn_frame, text="+ Note", font=("Segoe UI", 6), bg="#d1d8ff", command=add_note).pack(side="left", padx=4)

        def delete_selected():
            sel = tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            try:
                node["links"].pop(idx)
                node["modified"] = iso_now()
                refresh()
                self.save_project()
                self.redraw()
            except Exception:
                pass

        tk.Button(
            btn_frame,
            text="Delete",
            fg="red",
            font = ("Segoe UI", 6),
            command=delete_selected,
        ).pack(side="left")

        refresh()
        manager.update_idletasks()

    def edit_node_text(self, nid):
        new = simpledialog.askstring("Edit", "Text:", initialvalue=self.nodes[nid]["text"])
        if new:
            self.nodes[nid]["text"] = new
            self.nodes[nid]["modified"] = iso_now()
            self.save_project()
            # only apply sorting if a sort mode is active (to avoid overriding manual order)
            if self.settings.get("auto_sort", "None") != "None":
                self.apply_sorting()
            else:
                # keep manual_children in sync with children order
                parent = self.find_parent(nid)
                if parent:
                    self.nodes[parent]["manual_children"] = list(self.nodes[parent]["children"])
            self.redraw()

    def add_branch(self):
        if not self.selected:
            return
        name = simpledialog.askstring("New", "Name:")
        if name:
            cid = f"n_{len(self.nodes)}_{os.urandom(2).hex()}"
            now = iso_now()
            self.nodes[cid] = {
                "text": name,
                "children": [],
                "pos": [0, 0],
                "expanded": True,
                "links": [],
                "color": DEFAULT_NODE_COLOR,
                "modified": now,
                "manual_children": [],
            }
            self.nodes[self.selected]["children"].append(cid)
            self.nodes[self.selected]["modified"] = now
            # update manual_children if in manual mode
            if self.settings.get("auto_sort", "None") == "None":
                self.nodes[self.selected]["manual_children"] = list(self.nodes[self.selected]["children"])
            else:
                self.apply_sorting()
            self.reorganize_and_zoom()

    def delete_node(self):
        if self.selected != self.root_id:
            for n in self.nodes.values():
                if self.selected in n["children"]:
                    n["children"].remove(self.selected)
                    n["modified"] = iso_now()
                    if "manual_children" in n:
                        # remove from saved manual ordering
                        n["manual_children"] = [c for c in n.get("manual_children", []) if c != self.selected]
            try:
                del self.nodes[self.selected]
            except KeyError:
                pass
            # keep manual order if None, otherwise apply sorting
            if self.settings.get("auto_sort", "None") != "None":
                self.apply_sorting()
            self.reorganize_and_zoom()
            self.update_toolbar_buttons()

    def expand_all(self):
        for n in self.nodes.values():
            n["expanded"] = True
        self.reorganize_and_zoom()

    def collapse_all(self):
        for nid, n in self.nodes.items():
            if nid != self.root_id:
                n["expanded"] = False
        self.reorganize_and_zoom()

    # --- Manual reorder helpers ---
    def find_parent(self, child_id):
        for pid, node in self.nodes.items():
            if child_id in node.get("children", []):
                return pid
        return None

    def move_selected_up(self):
        if not self.selected or self.selected == self.root_id:
            return
        if self.settings.get("auto_sort", "None") != "None":
            # disabled under sort modes
            return
        parent = self.find_parent(self.selected)
        if not parent:
            return
        children = self.nodes[parent]["children"]
        idx = children.index(self.selected)
        if idx > 0:
            children[idx], children[idx - 1] = children[idx - 1], children[idx]
            # keep manual record
            self.nodes[parent]["manual_children"] = list(children)
            self.nodes[parent]["modified"] = iso_now()
            self.save_project()
            self.reorganize_and_zoom()
            self.redraw()
            self.update_toolbar_buttons()

    def move_selected_down(self):
        if not self.selected or self.selected == self.root_id:
            return
        if self.settings.get("auto_sort", "None") != "None":
            return
        parent = self.find_parent(self.selected)
        if not parent:
            return
        children = self.nodes[parent]["children"]
        idx = children.index(self.selected)
        if idx < len(children) - 1:
            children[idx], children[idx + 1] = children[idx + 1], children[idx]
            self.nodes[parent]["manual_children"] = list(children)
            self.nodes[parent]["modified"] = iso_now()
            self.save_project()
            self.reorganize_and_zoom()
            self.redraw()
            self.update_toolbar_buttons()

    def update_toolbar_buttons(self):
        """
        Enable/disable the right-toolbar up/down icons depending on:
        - a node is selected (and is not root)
        - current sort mode is 'None' (manual ordering)
        Also keep visual feedback.
        """
        manual = self.settings.get("auto_sort", "None") == "None"
        if not manual or not self.selected or self.selected == self.root_id:
            self.icon_up.config(state="disabled")
            self.icon_down.config(state="disabled")
            return

        parent = self.find_parent(self.selected)
        if not parent:
            self.icon_up.config(state="disabled")
            self.icon_down.config(state="disabled")
            return

        children = self.nodes[parent]["children"]
        idx = children.index(self.selected)
        if idx > 0:
            self.icon_up.config(state="normal")
        else:
            self.icon_up.config(state="disabled")
        if idx < len(children) - 1:
            self.icon_down.config(state="normal")
        else:
            self.icon_down.config(state="disabled")

    # --- EXPORT / PRINTING HELPERS ---
    def _export_canvas_postscript(self, scale=1):
        """
        Returns PostScript bytes for the current canvas.
        scale: multiplier to increase PS resolution (best-effort).
        """
        # Ensure the canvas has the latest drawing
        self.canvas.update_idletasks()
        width = int(self.canvas.winfo_width() * scale)
        height = int(self.canvas.winfo_height() * scale)
        # Use postscript export. Note: PostScript is generated at 72 DPI, scaling helps resolution.
        ps = self.canvas.postscript(colormode="color", width=width, height=height, pagewidth=width, pageheight=height)
        return ps.encode("utf-8")

    def _postscript_to_image(self, ps_bytes):
        """
        Convert PostScript bytes to a PIL Image.
        Requires Pillow + Ghostscript available in the environment.
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow is not installed. Install it with 'pip install Pillow' and ensure Ghostscript is available.")

        # Write to temporary .ps file because PIL expects a file-like EPS/PS with correct header
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ps") as tf:
            tf.write(ps_bytes)
            tf.flush()
            temp_ps = tf.name

        try:
            # Pillow will invoke Ghostscript for PostScript/EPS conversions.
            img = Image.open(temp_ps)
            # Force load (runs conversion)
            img.load()
            # Convert to RGBA to make background handling easier
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            # Add white background behind any transparency
            bg = Image.new("RGBA", img.size, "WHITE")
            bg.paste(img, mask=img.split()[3] if len(img.split()) >= 4 else None)
            final = bg.convert("RGB")
            return final
        finally:
            try:
                os.unlink(temp_ps)
            except Exception:
                pass

    def export_as_png(self):
        """
        Export the visible canvas to a PNG file chosen by the user.
        """
        if not PIL_AVAILABLE:
            messagebox.showerror("Export failed", "Export requires Pillow. Install with 'pip install Pillow' and Ghostscript available on PATH.")
            return

        # Ask for filename
        out_path = filedialog.asksaveasfilename(title="Export as PNG", defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not out_path:
            return

        try:
            # Try a higher scale for better quality
            scale = 2
            ps_bytes = self._export_canvas_postscript(scale=scale)
            img = self._postscript_to_image(ps_bytes)
            # If we scaled, resize down to expected pixel dimensions for cleaner rendering (optional)
            # Save PNG
            img.save(out_path, "PNG")
            messagebox.showinfo("Export complete", f"Canvas exported as PNG:\n{out_path}")
        except Exception as ex:
            messagebox.showerror("Export failed", f"Could not export canvas to PNG:\n{ex}")

    def export_as_pdf(self):
        """
        Export the visible canvas to a PDF file chosen by the user.
        """
        if not PIL_AVAILABLE:
            messagebox.showerror("Export failed", "Export requires Pillow. Install with 'pip install Pillow' and Ghostscript available on PATH.")
            return

        out_path = filedialog.asksaveasfilename(title="Export as PDF", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out_path:
            return

        try:
            scale = 2
            ps_bytes = self._export_canvas_postscript(scale=scale)
            img = self._postscript_to_image(ps_bytes)
            # Save as PDF (RGB)
            img.save(out_path, "PDF", resolution=150.0)
            messagebox.showinfo("Export complete", f"Canvas exported as PDF:\n{out_path}")
        except Exception as ex:
            messagebox.showerror("Export failed", f"Could not export canvas to PDF:\n{ex}")

    # --- Node color helpers ---
    def set_node_color(self, nid):
        """
        Open a color chooser to set a node's fill color.
        """
        if nid not in self.nodes:
            return
        initial = self.nodes[nid].get("color", DEFAULT_NODE_COLOR)
        # askcolor returns ( (r,g,b), "#rrggbb" ) or (None, None) if canceled
        rgb, hex_color = colorchooser.askcolor(color=initial, title="Choose node color")
        if hex_color is None:
            return
        self.nodes[nid]["color"] = hex_color
        self.nodes[nid]["modified"] = iso_now()
        self.save_project()
        # preserve manual order if None, else re-sort
        if self.settings.get("auto_sort", "None") != "None":
            self.apply_sorting()
        else:
            # update manual_children for parent so manual order persists
            parent = self.find_parent(nid)
            if parent:
                self.nodes[parent]["manual_children"] = list(self.nodes[parent]["children"])
        self.redraw()

    def clear_node_color(self, nid):
        """
        Reset node color to default.
        """
        if nid not in self.nodes:
            return
        # Keep the key for compatibility, but set to default
        self.nodes[nid]["color"] = DEFAULT_NODE_COLOR
        self.nodes[nid]["modified"] = iso_now()
        self.save_project()
        if self.settings.get("auto_sort", "None") != "None":
            self.apply_sorting()
        else:
            parent = self.find_parent(nid)
            if parent:
                self.nodes[parent]["manual_children"] = list(self.nodes[parent]["children"])
        self.redraw()


if __name__ == "__main__":
    root = tk.Tk()

    # ---- FORCE TK SCALING (CRITICAL) ----
    scaling = root.winfo_fpixels('1i') / 72
    root.tk.call('tk', 'scaling', scaling)

    app = MindMapApp(root)
    root.mainloop()