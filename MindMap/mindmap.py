import tkinter as tk
from tkinter import simpledialog, messagebox, Menu, filedialog, ttk
import json
import os
import webbrowser
import platform
import subprocess


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
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.root.quit)

        # --- TOOLBAR ---
        self.toolbar = tk.Frame(self.root, bg="#f5f5f7")
        self.toolbar.pack(fill="x", side="top")

        # ADDED REORGANIZE BUTTON
        tk.Button(self.toolbar, text="Reorganize Map", command=self.reorganize_and_zoom, bg="#c8e6c9",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=5, pady=3)

        tk.Button(self.toolbar, text="Zoom All", command=self.zoom_all, bg="#d1d8ff",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Expand All", command=self.expand_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Collapse All", command=self.collapse_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Help", command=self.show_help).pack(side="right", padx=10, pady=3)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status_var, bd=1, relief="sunken", anchor="w", bg="#f0f0f0").pack(
            side="bottom", fill="x")

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

        # Bindings
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.do_pan)
        self.canvas.bind("<MouseWheel>", self.on_mouse_zoom)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        self.load_project()
        self.root.after(500, self.reorganize_and_zoom)

    # --- AUTO-LAYOUT LOGIC ---
    def reorganize_nodes(self):
        """Calculates optimal tree positions recursively."""
        if not self.nodes: return

        self.next_y = 0
        v_gap = 80  # Vertical space between nodes
        h_gap = 220  # Horizontal space between levels

        def layout_recursive(nid, depth):
            node = self.nodes[nid]
            x_pos = depth * h_gap

            # If node is leaf or collapsed, it takes up one 'slot' of Y space
            if not node.get("expanded", True) or not node["children"]:
                y_pos = self.next_y
                node["pos"] = [x_pos, y_pos]
                self.next_y += v_gap
                return y_pos
            else:
                # Parent node: Layout all children first
                child_ys = []
                for cid in node["children"]:
                    if cid in self.nodes:
                        child_ys.append(layout_recursive(cid, depth + 1))

                # Center the parent between its top and bottom child
                actual_y = (child_ys[0] + child_ys[-1]) / 2
                node["pos"] = [x_pos, actual_y]
                return actual_y

        layout_recursive(self.root_id, 0)
        self.save_project()

    def reorganize_and_zoom(self):
        self.reorganize_nodes()
        self.zoom_all()

    def on_left_click(self, e):
        wx, wy = self.to_world(e.x, e.y)
        clicked_node = self.find_node_at(e.x, e.y)
        if clicked_node:
            nx, ny = self.nodes[clicked_node]["pos"]
            px = 75
            if (nx + px - 15) < wx < (nx + px + 15) and (ny - 15) < wy < (ny + 15):
                self.selected = clicked_node
                self.add_branch()
                return
            self.selected = clicked_node
            self.dragging = self.selected
        else:
            self.drag_box_start = (e.x, e.y)

    def on_drag(self, e):
        if self.dragging:
            self.nodes[self.dragging]["pos"] = self.to_world(e.x, e.y)
            self.redraw()
        elif self.drag_box_start:
            self.redraw()
            x0, y0 = self.drag_box_start
            color = "#3498db" if (e.x > x0 and e.y > y0) else "#2ecc71"
            self.canvas.create_rectangle(x0, y0, e.x, e.y, outline=color, dash=(4, 4), width=2)

    def on_release(self, e):
        if self.drag_box_start:
            x0, y0 = self.drag_box_start
            if e.x < x0 or e.y < y0:
                if abs(e.x - x0) > 10: self.zoom_all()
            else:
                if abs(e.x - x0) > 10 and abs(e.y - y0) > 10:
                    self.box_zoom(x0, y0, e.x, e.y)
            self.drag_box_start = None
            self.redraw()
        if self.dragging:
            self.save_project()
            self.dragging = None

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
        factor = 1.1 if e.delta > 0 else 0.9
        mx, my = self.to_world(e.x, e.y)
        self.zoom_level *= factor
        self.zoom_level = max(0.1, min(self.zoom_level, 5.0))
        self.offset_x = e.x - mx * self.zoom_level
        self.offset_y = e.y - my * self.zoom_level
        self.redraw()

    def do_pan(self, e):
        self.offset_x += (e.x - self.pan_last_x)
        self.offset_y += (e.y - self.pan_last_y)
        self.pan_last_x, self.pan_last_y = e.x, e.y
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")

        def draw_tree(nid, depth=0):
            node = self.nodes[nid]
            sx, sy = self.to_screen(*node["pos"])
            if node.get("expanded", True):
                for cid in node["children"]:
                    if cid in self.nodes:
                        cx, cy = self.to_screen(*self.nodes[cid]["pos"])
                        # Connection Arrows/Lines
                        self.canvas.create_line(sx, sy, (sx + cx) / 2, sy, (sx + cx) / 2, cy, cx, cy, smooth=True,
                                                fill="#dcdde1", width=max(1, int(2 * self.zoom_level)))
                        draw_tree(cid, depth + 1)

            px, py = 75 * self.zoom_level, 20 * self.zoom_level
            color = ["#4834d4", "#686de0", "#eb4d4b", "#6ab04c"][depth % 4]
            self.canvas.create_rectangle(sx - px, sy - py, sx + px, sy + py, fill="white", outline=color,
                                         width=max(1, int(2 * self.zoom_level)))
            self.canvas.create_text(sx, sy, text=node["text"],
                                    font=("Segoe UI", max(5, int(10 * self.zoom_level)), "bold"))

            # Plus icon
            btn_r = 8 * self.zoom_level
            self.canvas.create_oval(sx + px - btn_r, sy - btn_r, sx + px + btn_r, sy + btn_r,
                                    fill="white", outline=color, width=1)
            self.canvas.create_text(sx + px, sy, text="+", fill=color,
                                    font=("Segoe UI", max(6, int(9 * self.zoom_level)), "bold"))

            if not node.get("expanded", True) and node["children"]:
                self.canvas.create_text(sx + px - 12, sy + py - 8, text=f"({len(node['children'])})",
                                        font=("Segoe UI", max(5, int(7 * self.zoom_level))), fill="#636e72")

            if node.get("links"):
                self.canvas.create_text(sx - px + 12, sy, text="🔗", font=("Segoe UI", max(5, int(8 * self.zoom_level))))

        if self.nodes: draw_tree(self.root_id)

    def to_screen(self, wx, wy):
        return (wx * self.zoom_level) + self.offset_x, (wy * self.zoom_level) + self.offset_y

    def to_world(self, sx, sy):
        return (sx - self.offset_x) / self.zoom_level, (sy - self.offset_y) / self.zoom_level

    def zoom_all(self):
        if not self.nodes: return
        v_coords = []

        def collect_v(nid):
            v_coords.append(self.nodes[nid]["pos"])
            if self.nodes[nid].get("expanded", True):
                for cid in self.nodes[nid]["children"]:
                    if cid in self.nodes: collect_v(cid)

        collect_v(self.root_id)
        all_x = [p[0] for p in v_coords];
        all_y = [p[1] for p in v_coords]
        min_wx, max_wx = min(all_x) - 100, max(all_x) + 100
        min_wy, max_wy = min(all_y) - 60, max(all_y) + 60
        sw, sh = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        self.zoom_level = min(sw / max(max_wx - min_wx, 1), sh / max(max_wy - min_wy, 1), 1.5)
        self.offset_x = (sw / 2) - ((min_wx + max_wx) / 2) * self.zoom_level
        self.offset_y = (sh / 2) - ((min_wy + max_wy) / 2) * self.zoom_level
        self.redraw()

    def show_help(self):
        h = ("NEW: Reorganize Button\n"
             "- Click 'Reorganize Map' to auto-align all branches into an optimal tree layout.\n\n"
             "- Click the '+' icon to add a child.\n"
             "- Right-Drag: Pan.\n"
             "- Double-Click: Collapse/Expand or Edit.")
        messagebox.showinfo("Help", h)

    def load_settings(self):
        if os.path.exists(self.settings_path):
            with open(self.settings_path, "r") as f: return json.load(f)
        return {"last_project": "central.json", "recent": []}

    def save_settings(self):
        with open(self.settings_path, "w") as f: json.dump(self.settings, f, indent=2)

    def update_recent_list(self, filename):
        recents = self.settings.get("recent", [])
        if filename in recents: recents.remove(filename)
        recents.insert(0, filename)
        self.settings["recent"] = recents[:5]
        self.settings["last_project"] = filename
        self.save_settings()
        self.update_recent_menu()

    def update_recent_menu(self):
        self.recent_menu.delete(0, "end")
        for file in self.settings.get("recent", []):
            self.recent_menu.add_command(label=file, command=lambda f=file: self.switch_project(f))

    def switch_project(self, filename):
        self.current_project = filename
        self.load_project();
        self.update_title();
        self.update_recent_list(filename);
        self.reorganize_and_zoom()

    def new_project(self):
        name = simpledialog.askstring("New", "Project Name:")
        if name:
            if not name.endswith(".json"): name += ".json"
            self.current_project = name
            self.nodes = {
                self.root_id: {"text": "Central Idea", "children": [], "pos": (0, 0), "expanded": True, "links": []}}
            self.save_project();
            self.update_recent_list(name);
            self.update_title();
            self.reorganize_and_zoom()

    def open_project(self):
        path = filedialog.askopenfilename(initialdir=self.projects_dir, filetypes=[("JSON", "*.json")])
        if path: self.switch_project(os.path.basename(path))

    def save_as_project(self):
        path = filedialog.asksaveasfilename(initialdir=self.projects_dir, defaultextension=".json")
        if path:
            self.current_project = os.path.basename(path)
            self.save_project();
            self.update_recent_list(self.current_project);
            self.update_title()

    def update_title(self):
        self.root.title(f"Mind Map Pro - [{self.current_project}]")

    def save_project(self):
        with open(os.path.join(self.projects_dir, self.current_project), "w") as f: json.dump(self.nodes, f, indent=2)

    def load_project(self):
        p = os.path.join(self.projects_dir, self.current_project)
        if os.path.exists(p):
            with open(p, "r") as f:
                self.nodes = json.load(f)
            for n in self.nodes.values(): n.setdefault("links", [])
        else:
            self.nodes = {
                self.root_id: {"text": "Central Idea", "children": [], "pos": (0, 0), "expanded": True, "links": []}}

    def find_node_at(self, x, y):
        wx, wy = self.to_world(x, y)
        for nid, node in self.nodes.items():
            nx, ny = node["pos"]
            if nx - 75 < wx < nx + 85 and ny - 25 < wy < ny + 25: return nid
        return None

    def on_right_press(self, e):
        self.pan_last_x, self.pan_last_y = e.x, e.y
        self.show_right_click_menu(e)

    def show_right_click_menu(self, event):
        self.selected = self.find_node_at(event.x, event.y)
        menu = Menu(self.root, tearoff=0)
        if self.selected:
            menu.add_command(label="Resources...", command=lambda: self.manage_resources(self.selected))
            menu.add_command(label="Edit Text", command=lambda: self.edit_node_text(self.selected))
            menu.add_command(label="Add Branch", command=self.add_branch)
            menu.add_command(label="Delete", command=self.delete_node, foreground="red")
        else:
            menu.add_command(label="Reorganize & Zoom", command=self.reorganize_and_zoom)
        menu.post(event.x_root, event.y_root)

    def on_double_click(self, e):
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
        manager.geometry("650x450")
        f = tk.Frame(manager);
        f.pack(fill="both", expand=True, padx=10, pady=10)
        tree = ttk.Treeview(f, columns=("Type", "Path"), show="headings")
        tree.heading("Type", text="Type");
        tree.heading("Path", text="Path / URL")
        tree.column("Type", width=70, anchor="center");
        tree.column("Path", width=480)
        tree.pack(side="left", fill="both", expand=True)
        vs = tk.Scrollbar(f, command=tree.yview);
        vs.pack(side="right", fill="y")
        tree.config(yscrollcommand=vs.set)

        def refresh():
            for i in tree.get_children(): tree.delete(i)
            for l in node.get("links", []):
                r_type = "🌐 Web" if l.startswith("http") else "📄 File"
                tree.insert("", "end", values=(r_type, l))

        def open_selected(e=None):
            sel = tree.selection()
            if sel: webbrowser.open(tree.item(sel[0])['values'][1])

        tree.bind("<Double-1>", open_selected)
        btn_f = tk.Frame(manager);
        btn_f.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_f, text="+ Add URL",
                  command=lambda: [node.setdefault("links", []).append(simpledialog.askstring("URL", "Address:")),
                                   refresh(), self.save_project(), self.redraw()]).pack(side="left", padx=2)
        tk.Button(btn_f, text="+ Add File",
                  command=lambda: [node.setdefault("links", []).append(filedialog.askopenfilename()), refresh(),
                                   self.save_project(), self.redraw()]).pack(side="left", padx=2)
        tk.Button(btn_f, text="Delete Selected", fg="red",
                  command=lambda: [node["links"].remove(tree.item(tree.selection()[0])['values'][1]), refresh(),
                                   self.save_project(), self.redraw()] if tree.selection() else None).pack(side="left")
        refresh()

    def edit_node_text(self, nid):
        new = simpledialog.askstring("Edit", "Text:", initialvalue=self.nodes[nid]["text"])
        if new:
            self.nodes[nid]["text"] = new;
            self.save_project();
            self.redraw()

    def add_branch(self):
        if not self.selected: return
        name = simpledialog.askstring("New", "Name:")
        if name:
            cid = f"n_{len(self.nodes)}_{os.urandom(2).hex()}"
            self.nodes[cid] = {"text": name, "children": [], "pos": [0, 0], "expanded": True, "links": []}
            self.nodes[self.selected]["children"].append(cid)
            self.reorganize_and_zoom()

    def delete_node(self):
        if self.selected != self.root_id:
            for n in self.nodes.values():
                if self.selected in n["children"]: n["children"].remove(self.selected)
            del self.nodes[self.selected];
            self.reorganize_and_zoom()

    def expand_all(self):
        for n in self.nodes.values(): n["expanded"] = True
        self.reorganize_and_zoom()

    def collapse_all(self):
        for nid, n in self.nodes.items():
            if nid != self.root_id: n["expanded"] = False
        self.reorganize_and_zoom()


if __name__ == "__main__":
    root = tk.Tk()
    app = MindMapApp(root)
    root.mainloop()