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
        tk.Button(self.toolbar, text="Zoom All", command=self.zoom_all, bg="#d1d8ff",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Expand All", command=self.expand_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Collapse All", command=self.collapse_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Help", command=self.show_help).pack(side="right", padx=10, pady=3)
        tk.Button(self.toolbar, text="Project Info", command=self.show_project_info).pack(side="right", padx=5, pady=3)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status_var, bd=1, relief="sunken", anchor="w", bg="#f0f0f0").pack(
            side="bottom", fill="x")

        # --- CANVAS & MINIMAP ---
        self.canvas = tk.Canvas(self.root, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.mini_w, self.mini_h = 200, 150
        self.minimap = tk.Canvas(self.root, width=self.mini_w, height=self.mini_h, bg="#fdfdfd", highlightthickness=1,
                                 highlightbackground="#ccc")
        self.minimap.place(relx=1.0, rely=1.0, x=-20, y=-40, anchor="se")

        self.zoom_level = 1.0
        self.offset_x, self.offset_y = 700, 450
        self.pan_last_x, self.pan_last_y = 0, 0
        self.nodes = {}
        self.root_id = "root"
        self.selected = None
        self.dragging = None

        # Bindings
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.do_pan)
        self.canvas.bind("<MouseWheel>", self.on_mouse_scroll_v)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        self.load_project()
        self.root.after(500, self.zoom_all)

    # --- UPDATED INTERACTION (AUTO-FIT) ---
    def on_double_click(self, e):
        nid = self.find_node_at(e.x, e.y)
        if nid:
            if self.nodes[nid].get("links"):
                self.manage_resources(nid)
            elif self.nodes[nid]["children"]:
                # Toggle expansion
                self.nodes[nid]["expanded"] = not self.nodes[nid].get("expanded", True)
                # Auto-fit view to include new objects
                self.zoom_all()
            else:
                self.edit_node_text(nid)

    # --- RESOURCE MANAGER ---
    def manage_resources(self, nid):
        node = self.nodes[nid]
        manager = tk.Toplevel(self.root)
        manager.title(f"Resources: {node['text']}")
        manager.geometry("650x450")
        manager.transient(self.root)

        f = tk.Frame(manager)
        f.pack(fill="both", expand=True, padx=10, pady=10)

        tree = ttk.Treeview(f, columns=("Type", "Path"), show="headings")
        tree.heading("Type", text="Type")
        tree.heading("Path", text="Path / URL")
        tree.column("Type", width=70, anchor="center")
        tree.column("Path", width=480)
        tree.pack(side="left", fill="both", expand=True)

        vs = tk.Scrollbar(f, command=tree.yview)
        vs.pack(side="right", fill="y")
        tree.config(yscrollcommand=vs.set)

        def refresh():
            for i in tree.get_children(): tree.delete(i)
            for l in node.get("links", []):
                r_type = "🌐 Web" if l.startswith("http") else "📄 File"
                tree.insert("", "end", values=(r_type, l))

        def copy_selected():
            sel = tree.selection()
            if sel:
                val = tree.item(sel[0])['values'][1]
                self.root.clipboard_clear()
                self.root.clipboard_append(val)
                self.status_var.set("Copied to clipboard!")

        def open_selected(e=None):
            sel = tree.selection()
            if sel: webbrowser.open(tree.item(sel[0])['values'][1])

        tree.bind("<Double-1>", open_selected)

        btn_f = tk.Frame(manager)
        btn_f.pack(fill="x", pady=10, padx=10)

        tk.Button(btn_f, text="+ Add URL",
                  command=lambda: [node.setdefault("links", []).append(simpledialog.askstring("URL", "Address:")),
                                   refresh(), self.save_project(), self.redraw()]).pack(side="left", padx=2)
        tk.Button(btn_f, text="+ Add File",
                  command=lambda: [node.setdefault("links", []).append(filedialog.askopenfilename()), refresh(),
                                   self.save_project(), self.redraw()]).pack(side="left", padx=2)
        tk.Button(btn_f, text="Copy Path", command=copy_selected).pack(side="left", padx=2)
        tk.Button(btn_f, text="Open", command=open_selected, bg="#e1f5fe").pack(side="left", padx=2)

        bottom_f = tk.Frame(manager)
        bottom_f.pack(fill="x", side="bottom", pady=10, padx=10)

        tk.Button(bottom_f, text="Close", width=10, command=manager.destroy).pack(side="right")
        tk.Button(bottom_f, text="Delete Selected", fg="red",
                  command=lambda: [node["links"].remove(tree.item(tree.selection()[0])['values'][1]), refresh(),
                                   self.save_project(), self.redraw()] if tree.selection() else None).pack(side="left")

        refresh()

    # --- ZOOM ALL (VISIBLE ONLY) ---
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
        win_w, win_h = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        self.zoom_level = min(win_w / max(max_wx - min_wx, 1), win_h / max(max_wy - min_wy, 1), 1.5)
        self.offset_x = (win_w / 2) - ((min_wx + max_wx) / 2) * self.zoom_level
        self.offset_y = (win_h / 2) - ((min_wy + max_wy) / 2) * self.zoom_level
        self.redraw()

    # --- PROJECT & SETTINGS ---
    def load_settings(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"last_project": "central.json", "recent": []}

    def save_settings(self):
        with open(self.settings_path, "w") as f: json.dump(self.settings, f, indent=2)

    def update_recent_list(self, filename):
        recents = self.settings.get("recent", [])
        if filename in recents: recents.remove(filename)
        recents.insert(0, filename)
        self.settings["recent"] = recents[:5]
        self.settings["last_project"] = filename
        self.save_settings();
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
        self.zoom_all()

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
            self.zoom_all()

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

    # --- DRAWING ---
    def to_screen(self, wx, wy):
        return (wx * self.zoom_level) + self.offset_x, (wy * self.zoom_level) + self.offset_y

    def to_world(self, sx, sy):
        return (sx - self.offset_x) / self.zoom_level, (sy - self.offset_y) / self.zoom_level

    def redraw(self):
        self.canvas.delete("all")

        def draw_tree(nid, depth=0):
            node = self.nodes[nid]
            sx, sy = self.to_screen(*node["pos"])
            if node.get("expanded", True):
                for cid in node["children"]:
                    if cid in self.nodes:
                        cx, cy = self.to_screen(*self.nodes[cid]["pos"])
                        self.canvas.create_line(sx, sy, (sx + cx) / 2, sy, (sx + cx) / 2, cy, cx, cy, smooth=True,
                                                fill="#dcdde1", width=max(1, int(2 * self.zoom_level)))
                        draw_tree(cid, depth + 1)
            px, py = 75 * self.zoom_level, 20 * self.zoom_level
            color = ["#4834d4", "#686de0", "#eb4d4b", "#6ab04c"][depth % 4]
            self.canvas.create_rectangle(sx - px, sy - py, sx + px, sy + py, fill="white", outline=color,
                                         width=max(1, int(2 * self.zoom_level)))
            self.canvas.create_text(sx, sy, text=node["text"],
                                    font=("Segoe UI", max(5, int(10 * self.zoom_level)), "bold"))
            if not node.get("expanded", True) and node["children"]:
                self.canvas.create_text(sx + px - 12, sy + py - 8, text=f"+({len(node['children'])})",
                                        font=("Segoe UI", max(5, int(7 * self.zoom_level))), fill="#636e72")
            if node.get("links"): self.canvas.create_text(sx - px + 12, sy, text="🔗",
                                                          font=("Segoe UI", max(5, int(8 * self.zoom_level))))

        if self.nodes: draw_tree(self.root_id); self.draw_minimap()

    def draw_minimap(self):
        self.minimap.delete("all")
        all_x = [n["pos"][0] for n in self.nodes.values()];
        all_y = [n["pos"][1] for n in self.nodes.values()]
        min_wx, max_wx = min(all_x) - 400, max(all_x) + 400
        min_wy, max_wy = min(all_y) - 400, max(all_y) + 400
        m_scale = min(self.mini_w / max(1, max_wx - min_wx), self.mini_h / max(1, max_wy - min_wy))

        def to_m(wx, wy): return (wx - min_wx) * m_scale, (wy - min_wy) * m_scale

        for n in self.nodes.values():
            mx, my = to_m(*n["pos"])
            self.minimap.create_oval(mx - 1, my - 1, mx + 1, my + 1, fill="#4834d4", outline="")
        v_tl, v_br = self.to_world(0, 0), self.to_world(self.canvas.winfo_width(), self.canvas.winfo_height())
        m_tl, m_br = to_m(*v_tl), to_m(*v_br)
        self.minimap.create_rectangle(m_tl[0], m_tl[1], m_br[0], m_br[1], outline="red")

    # --- INPUT ---
    def do_pan(self, e):
        self.offset_x += (e.x - self.pan_last_x);
        self.offset_y += (e.y - self.pan_last_y)
        self.pan_last_x, self.pan_last_y = e.x, e.y;
        self.redraw()

    def on_right_press(self, e):
        self.pan_last_x, self.pan_last_y = e.x, e.y; self.show_right_click_menu(e)

    def on_left_click(self, e):
        self.selected = self.find_node_at(e.x, e.y); self.dragging = self.selected

    def on_drag(self, e):
        if self.dragging: self.nodes[self.dragging]["pos"] = self.to_world(e.x, e.y); self.redraw()

    def on_release(self, e):
        if self.dragging: self.save_project(); self.dragging = None

    def on_mouse_scroll_v(self, e):
        self.offset_y += (e.delta / 2); self.redraw()

    def find_node_at(self, x, y):
        wx, wy = self.to_world(x, y)
        for nid, node in self.nodes.items():
            nx, ny = node["pos"]
            if nx - 75 < wx < nx + 75 and ny - 20 < wy < ny + 20: return nid
        return None

    def show_right_click_menu(self, event):
        self.selected = self.find_node_at(event.x, event.y)
        menu = Menu(self.root, tearoff=0)
        if self.selected:
            menu.add_command(label="Manage Resources...", command=lambda: self.manage_resources(self.selected))
            menu.add_command(label="Edit Text", command=lambda: self.edit_node_text(self.selected))
            menu.add_command(label="Add Branch", command=self.add_branch)
            menu.add_command(label="Delete Node", command=self.delete_node, foreground="red")
        else:
            menu.add_command(label="Zoom All", command=self.zoom_all)
        menu.post(event.x_root, event.y_root)

    def edit_node_text(self, nid):
        new = simpledialog.askstring("Edit", "Text:", initialvalue=self.nodes[nid]["text"])
        if new: self.nodes[nid]["text"] = new; self.save_project(); self.redraw()

    def add_branch(self):
        name = simpledialog.askstring("New", "Name:")
        if name:
            cid = f"n_{len(self.nodes)}_{os.urandom(2).hex()}"
            px, py = self.nodes[self.selected]["pos"]
            self.nodes[cid] = {"text": name, "children": [], "pos": (px + 200, py), "expanded": True, "links": []}
            self.nodes[self.selected]["children"].append(cid);
            self.save_project();
            self.redraw()

    def delete_node(self):
        if self.selected != self.root_id:
            for n in self.nodes.values():
                if self.selected in n["children"]: n["children"].remove(self.selected)
            del self.nodes[self.selected];
            self.save_project();
            self.redraw()

    def expand_all(self):
        for n in self.nodes.values(): n["expanded"] = True
        self.zoom_all()  # Added auto-zoom here too

    def collapse_all(self):
        for nid, n in self.nodes.items():
            if nid != self.root_id: n["expanded"] = False
        self.zoom_all()  # Added auto-zoom here too

    def show_help(self):
        h = ("AUTOMATION:\n- Expanding/Collapsing branches automatically fits the view to the screen.\n"
             "- Expand All / Collapse All now also auto-zoom.\n\n"
             "RESOURCES:\n- Double-Click list item to Open.\n"
             "- Use 'Close' button to exit resource manager.")
        messagebox.showinfo("Help", h)

    def show_project_info(self):
        info_win = tk.Toplevel(self.root)
        info_win.title("Project Info")
        info_win.geometry("400x200")
        tk.Label(info_win, text=f"Active: {self.current_project}\nPath: {self.projects_dir}", pady=20).pack()
        tk.Button(info_win, text="Open Folder", command=lambda: os.startfile(self.projects_dir)).pack()

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


if __name__ == "__main__":
    root = tk.Tk()
    app = MindMapApp(root)
    root.mainloop()