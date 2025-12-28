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

        # --- STATE ---
        self.projects_dir = os.path.abspath("projects")
        os.makedirs(self.projects_dir, exist_ok=True)
        self.current_project = "central.json"

        self.root.title(f"Mind Map Pro - [{self.current_project}]")
        self.root.geometry("1400x900")

        # --- UI LAYOUT ---
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

        # --- CANVAS ---
        self.canvas_frame = tk.Frame(self.root)
        self.canvas_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg="white", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        # --- MINIMAP CANVAS ---
        self.mini_w, self.mini_h = 200, 150
        self.minimap = tk.Canvas(self.root, width=self.mini_w, height=self.mini_h,
                                 bg="#fdfdfd", highlightthickness=1, highlightbackground="#ccc")
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
        self.canvas.bind("<Shift-MouseWheel>", self.on_mouse_scroll_h)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        self.load_project()
        self.root.after(500, self.zoom_all)

    # --- MINIMAP DRAWING ---
    def draw_minimap(self):
        self.minimap.delete("all")
        if not self.nodes: return

        # Calculate world bounds
        all_x = [n["pos"][0] for n in self.nodes.values()]
        all_y = [n["pos"][1] for n in self.nodes.values()]
        min_wx, max_wx = min(all_x) - 200, max(all_x) + 200
        min_wy, max_wy = min(all_y) - 200, max(all_y) + 200
        ww, wh = max_wx - min_wx, max_wy - min_wy

        # Scale for minimap
        m_scale = min(self.mini_w / ww, self.mini_h / wh)

        def to_mini(wx, wy):
            mx = (wx - min_wx) * m_scale
            my = (wy - min_wy) * m_scale
            return mx, my

        # Draw nodes as dots
        for n in self.nodes.values():
            mx, my = to_mini(*n["pos"])
            self.minimap.create_oval(mx - 2, my - 2, mx + 2, my + 2, fill="#4834d4", outline="")

        # Draw Viewport Rectangle
        v_tl = self.to_world(0, 0)
        v_br = self.to_world(self.canvas.winfo_width(), self.canvas.winfo_height())
        m_tl = to_mini(*v_tl)
        m_br = to_mini(*v_br)
        self.minimap.create_rectangle(m_tl[0], m_tl[1], m_br[0], m_br[1], outline="red", width=1)

    # --- ZOOM ALL (ROBUST RESET) ---
    def zoom_all(self):
        if not self.nodes: return

        all_x = [n["pos"][0] for n in self.nodes.values()]
        all_y = [n["pos"][1] for n in self.nodes.values()]

        min_wx, max_wx = min(all_x) - 150, max(all_x) + 150
        min_wy, max_wy = min(all_y) - 100, max(all_y) + 100

        world_w = max(max_wx - min_wx, 100)
        world_h = max(max_wy - min_wy, 100)

        win_w = max(self.canvas.winfo_width(), 100)
        win_h = max(self.canvas.winfo_height(), 100)

        self.zoom_level = min(win_w / world_w, win_h / world_h, 1.5)

        # Hard reset offsets to the center
        self.offset_x = (win_w / 2) - ((min_wx + max_wx) / 2) * self.zoom_level
        self.offset_y = (win_h / 2) - ((min_wy + max_wy) / 2) * self.zoom_level

        self.redraw()
        self.status_var.set(f"View Reset. Zoom: {int(self.zoom_level * 100)}%")

    # --- UPDATED PANNING ---
    def do_pan(self, e):
        dx = e.x - self.pan_last_x
        dy = e.y - self.pan_last_y
        self.offset_x += dx
        self.offset_y += dy
        self.pan_last_x, self.pan_last_y = e.x, e.y
        self.redraw()

    # --- RENDERING ---
    def to_screen(self, wx, wy):
        return (wx * self.zoom_level) + self.offset_x, (wy * self.zoom_level) + self.offset_y

    def to_world(self, sx, sy):
        return (sx - self.offset_x) / self.zoom_level, (sy - self.offset_y) / self.zoom_level

    def redraw(self):
        self.canvas.delete("all")

        # Optimization: Only draw tree if within a reasonable coordinate range
        def draw_tree(nid, depth=0):
            node = self.nodes[nid]
            sx, sy = self.to_screen(*node["pos"])
            expanded = node.get("expanded", True)
            if expanded:
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

            if not expanded and node["children"]:
                self.canvas.create_text(sx + px - 12, sy + py - 8, text=f"+({len(node['children'])})",
                                        font=("Segoe UI", max(5, int(7 * self.zoom_level))), fill="#636e72")
            if node.get("links"):
                self.canvas.create_text(sx - px + 12, sy, text="🔗", font=("Segoe UI", max(5, int(8 * self.zoom_level))))

        if self.nodes:
            draw_tree(self.root_id)
            self.draw_minimap()

    def show_help(self):
        messagebox.showinfo("Help",
                            "Right-Drag: Pan view\nLeft-Drag: Move node\nDouble-Click: Edit/Expand\nMinimap: Red box shows current view.")

    def show_project_info(self):
        info_win = tk.Toplevel(self.root)
        info_win.title("Project Info")
        info_win.geometry("400x200")
        tk.Label(info_win, text=f"Active: {self.current_project}\nPath: {self.projects_dir}", pady=20).pack()
        tk.Button(info_win, text="Open Folder", command=lambda: self.open_folder(self.projects_dir)).pack()

    def open_folder(self, path):
        if platform.system() == "Windows":
            os.startfile(path)
        else:
            subprocess.call(["open" if platform.system() == "Darwin" else "xdg-open", path])

    def on_right_press(self, e):
        self.pan_last_x, self.pan_last_y = e.x, e.y; self.show_right_click_menu(e)

    def on_mouse_scroll_v(self, e):
        self.offset_y += (e.delta / 2); self.redraw()

    def on_mouse_scroll_h(self, e):
        self.offset_x += (e.delta / 2); self.redraw()

    def on_left_click(self, e):
        self.selected = self.find_node_at(e.x, e.y); self.dragging = self.selected

    def on_drag(self, e):
        if self.dragging: self.nodes[self.dragging]["pos"] = self.to_world(e.x, e.y); self.redraw()

    def on_release(self, e):
        if self.dragging: self.save_project(); self.dragging = None

    def on_double_click(self, e):
        nid = self.find_node_at(e.x, e.y)
        if nid:
            if self.nodes[nid].get("links"):
                self.manage_resources(nid)
            elif self.nodes[nid]["children"]:
                self.nodes[nid]["expanded"] = not self.nodes[nid].get("expanded", True); self.redraw()
            else:
                self.edit_node_text(nid)

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

    def manage_resources(self, nid):
        node = self.nodes[nid]
        manager = tk.Toplevel(self.root)
        manager.title("Resources")
        tree = ttk.Treeview(manager, columns=("Path"), show="headings")
        tree.heading("Path", text="Path / URL");
        tree.pack(fill="both", expand=True)

        def refresh():
            for i in tree.get_children(): tree.delete(i)
            for l in node.get("links", []): tree.insert("", "end", values=(l,))

        refresh()
        btn_f = tk.Frame(manager);
        btn_f.pack(fill="x")
        tk.Button(btn_f, text="Add URL",
                  command=lambda: [node.setdefault("links", []).append(simpledialog.askstring("URL", "Address:")),
                                   refresh(), self.save_project(), self.redraw()]).pack(side="left")
        tk.Button(btn_f, text="Add File",
                  command=lambda: [node.setdefault("links", []).append(filedialog.askopenfilename()), refresh(),
                                   self.save_project(), self.redraw()]).pack(side="left")
        tk.Button(btn_f, text="Open", command=lambda: self.open_resource(
            tree.item(tree.selection()[0])['values'][0]) if tree.selection() else None).pack(side="left")
        refresh()

    def open_resource(self, path):
        if path.startswith("http"):
            webbrowser.open(path)
        else:
            self.open_folder(path)

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
        self.redraw()

    def collapse_all(self):
        for nid, n in self.nodes.items():
            if nid != self.root_id: n["expanded"] = False
        self.redraw()

    def save_project(self):
        with open(os.path.join(self.projects_dir, self.current_project), "w") as f: json.dump(self.nodes, f, indent=2)

    def load_project(self):
        p = os.path.join(self.projects_dir, self.current_project)
        if os.path.exists(p):
            with open(p, "r") as f:
                self.nodes = json.load(f)
        else:
            self.nodes = {
                self.root_id: {"text": "Central Idea", "children": [], "pos": (0, 0), "expanded": True, "links": []}}


if __name__ == "__main__":
    root = tk.Tk()
    app = MindMapApp(root)
    root.mainloop()