import tkinter as tk
from tkinter import simpledialog, messagebox, Menu
import json
import os


class MindMapApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mind Map Pro")
        self.root.geometry("1400x900")

        # --- UI LAYOUT ---
        self.toolbar = tk.Frame(self.root, bg="#f5f5f7")
        self.toolbar.pack(fill="x", side="top")

        tk.Button(self.toolbar, text="Zoom All", command=self.zoom_all, bg="#d1d8ff").pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Expand All", command=self.expand_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Collapse All", command=self.collapse_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Save Now", command=self.save_project).pack(side="left", padx=5, pady=3)

        self.canvas = tk.Canvas(self.root, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # --- VIEW STATE ---
        self.zoom_level = 1.0
        self.offset_x = 700
        self.offset_y = 450
        self.last_mouse_x = 0
        self.last_mouse_y = 0

        # --- DATA STATE ---
        self.projects_dir = "projects"
        os.makedirs(self.projects_dir, exist_ok=True)
        self.current_project = "central.json"
        self.nodes = {}
        self.root_id = "root"
        self.selected = None
        self.dragging = None

        # --- BINDINGS ---
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.do_pan)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        self.load_project()
        self.root.after(100, self.zoom_all)

    # --- COORDINATE CONVERSION ---
    def to_screen(self, world_x, world_y):
        return (world_x * self.zoom_level) + self.offset_x, (world_y * self.zoom_level) + self.offset_y

    def to_world(self, screen_x, screen_y):
        return (screen_x - self.offset_x) / self.zoom_level, (screen_y - self.offset_y) / self.zoom_level

    # --- NAVIGATION ---
    def on_zoom(self, event):
        old_zoom = self.zoom_level
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_level *= factor
        self.zoom_level = max(0.05, min(self.zoom_level, 10.0))
        mx, my = event.x, event.y
        self.offset_x = mx - (mx - self.offset_x) * (self.zoom_level / old_zoom)
        self.offset_y = my - (my - self.offset_y) * (self.zoom_level / old_zoom)
        self.redraw()

    def do_pan(self, event):
        if self.last_mouse_x != 0:
            self.offset_x += (event.x - self.last_mouse_x)
            self.offset_y += (event.y - self.last_mouse_y)
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.redraw()

    def zoom_all(self):
        if not self.nodes: return
        all_coords = []

        def collect_coords(nid):
            n = self.nodes[nid]
            all_coords.append(n["pos"])
            if n.get("expanded", True):
                for cid in n["children"]:
                    if cid in self.nodes: collect_coords(cid)

        collect_coords(self.root_id)
        all_x = [p[0] for p in all_coords];
        all_y = [p[1] for p in all_coords]
        min_x, max_x = min(all_x) - 80, max(all_x) + 80
        min_y, max_y = min(all_y) - 40, max(all_y) + 40
        map_w, map_h = max(1, max_x - min_x), max(1, max_y - min_y)
        win_w, win_h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        self.zoom_level = min(win_w / map_w, win_h / map_h, 1.5)
        self.offset_x = (win_w / 2) - ((min_x + max_x) / 2) * self.zoom_level
        self.offset_y = (win_h / 2) - ((min_y + max_y) / 2) * self.zoom_level
        self.redraw()

    # --- INTERACTION ---
    def find_node_at(self, x, y):
        wx, wy = self.to_world(x, y)
        for nid, node in self.nodes.items():
            nx, ny = node["pos"]
            if nx - 75 < wx < nx + 75 and ny - 20 < wy < ny + 20:
                return nid
        return None

    def on_left_click(self, event):
        self.last_mouse_x, self.last_mouse_y = 0, 0
        self.selected = self.find_node_at(event.x, event.y)
        self.dragging = self.selected

    def on_double_click(self, event):
        nid = self.find_node_at(event.x, event.y)
        if nid:
            node = self.nodes[nid]
            if node["children"]:
                node["expanded"] = not node.get("expanded", True)
            else:
                self.edit_node_data(nid)
            self.redraw()

    def on_right_click(self, event):
        self.last_mouse_x, self.last_mouse_y = event.x, event.y
        self.selected = self.find_node_at(event.x, event.y)

        menu = Menu(self.root, tearoff=0)
        if self.selected:
            # PRIORITY: Edit Data is now first
            menu.add_command(label="Edit Node", command=lambda: self.edit_node_data(self.selected))
            menu.add_separator()
            menu.add_command(label="Add Branch", command=self.add_branch)
            menu.add_command(label="Delete Node", command=self.delete_node, foreground="red")
        else:
            menu.add_command(label="Zoom to All", command=self.zoom_all)
            menu.add_command(label="New Project", command=self.new_project)

        menu.post(event.x_root, event.y_root)

    def on_drag(self, event):
        if self.dragging:
            self.nodes[self.dragging]["pos"] = self.to_world(event.x, event.y)
            self.redraw()

    def edit_node_data(self, nid=None):
        target_id = nid if nid else self.selected
        if not target_id: return

        node = self.nodes[target_id]
        new_text = simpledialog.askstring("Edit Node", "Enter new text:", initialvalue=node["text"])
        if new_text is not None:
            node["text"] = new_text
            self.redraw()

    def add_branch(self):
        if not self.selected: return
        name = simpledialog.askstring("New", "Branch name:")
        if not name: return
        cid = f"n_{len(self.nodes)}_{int(self.root.after_get('')) % 1000}"
        px, py = self.nodes[self.selected]["pos"]
        # Position child slightly to the right
        self.nodes[cid] = {"text": name, "children": [], "pos": (px + 200, py), "expanded": True}
        self.nodes[self.selected]["children"].append(cid)
        self.redraw()

    def delete_node(self):
        if self.selected == self.root_id or not self.selected: return
        for n in self.nodes.values():
            if self.selected in n["children"]: n["children"].remove(self.selected)
        del self.nodes[self.selected]
        self.selected = None
        self.redraw()

    # --- DRAWING ---
    def redraw(self):
        self.canvas.delete("all")
        # Background Grid
        g_step = 100
        for i in range(-20, 30):
            gx, _ = self.to_screen(i * g_step, 0)
            _, gy = self.to_screen(0, i * g_step)
            self.canvas.create_line(gx, -5000, gx, 5000, fill="#f8f8fa")
            self.canvas.create_line(-5000, gy, 5000, gy, fill="#f8f8fa")

        def draw_tree(nid, depth=0):
            if nid not in self.nodes: return
            node = self.nodes[nid]
            sx, sy = self.to_screen(*node["pos"])

            if node.get("expanded", True):
                for cid in node["children"]:
                    if cid in self.nodes:
                        cx, cy = self.to_screen(*self.nodes[cid]["pos"])
                        l_width = max(1, int(2 * self.zoom_level))
                        # Connect with curved lines
                        self.canvas.create_line(sx, sy, (sx + cx) / 2, sy, (sx + cx) / 2, cy, cx, cy,
                                                smooth=True, fill="#dcdde1", width=l_width)
                        draw_tree(cid, depth + 1)

            # Draw Node Shape
            px, py = 75 * self.zoom_level, 20 * self.zoom_level
            color = ["#4834d4", "#686de0", "#eb4d4b", "#6ab04c"][depth % 4]
            self.canvas.create_rectangle(sx - px, sy - py, sx + px, sy + py,
                                         fill="white", outline=color, width=max(1, int(2.5 * self.zoom_level)))

            f_size = max(4, int(10 * self.zoom_level))
            self.canvas.create_text(sx, sy, text=node["text"], font=("Segoe UI", f_size, "bold"), fill="#2f3640")

        draw_tree(self.root_id)

    def expand_all(self):
        for n in self.nodes.values(): n["expanded"] = True
        self.redraw()

    def collapse_all(self):
        for nid, n in self.nodes.items():
            if nid != self.root_id: n["expanded"] = False
        self.redraw()

    def save_project(self):
        path = os.path.join(self.projects_dir, self.current_project)
        with open(path, "w", encoding="utf-8") as f: json.dump(self.nodes, f, indent=2)
        messagebox.showinfo("Saved", "Project saved!")

    def load_project(self):
        path = os.path.join(self.projects_dir, self.current_project)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.nodes = json.load(f)
        else:
            self.nodes = {self.root_id: {"text": "Central Idea", "children": [], "pos": (0, 0), "expanded": True}}
        self.redraw()

    def new_project(self):
        name = simpledialog.askstring("New Project", "Enter project name:")
        if name:
            self.current_project = f"{name}.json"
            self.load_project()
            self.zoom_all()


if __name__ == "__main__":
    root = tk.Tk()
    app = MindMapApp(root)
    root.mainloop()