import tkinter as tk
from tkinter import simpledialog, messagebox, Menu, filedialog
import json
import os
import webbrowser
import platform
import subprocess


class MindMapApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mind Map Pro - Hub")
        self.root.geometry("1400x900")

        # --- UI LAYOUT ---
        self.toolbar = tk.Frame(self.root, bg="#f5f5f7")
        self.toolbar.pack(fill="x", side="top")

        tk.Button(self.toolbar, text="Zoom All", command=self.zoom_all, bg="#d1d8ff").pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Expand All", command=self.expand_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Collapse All", command=self.collapse_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Save Now", command=self.save_project).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Help", command=self.show_help).pack(side="right", padx=10, pady=3)

        # Status bar for link feedback
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief="sunken", anchor="w",
                                   bg="#f0f0f0")
        self.status_bar.pack(side="bottom", fill="x")

        self.canvas = tk.Canvas(self.root, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # --- STATE ---
        self.zoom_level = 1.0
        self.offset_x, self.offset_y = 700, 450
        self.last_mouse_x, self.last_mouse_y = 0, 0
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

    def show_help(self):
        help_text = (
                "🚀 MIND MAP PRO - FEATURE GUIDE\n" + "=" * 35 + "\n"
                                                                "🖱️ INTERACTION:\n"
                                                                " • Left Click: Select node (view link in status bar) or Drag to move.\n"
                                                                " • Double Click: Open Link (if exists) > Toggle Expand > Edit Text.\n"
                                                                " • Right Click: Context Menu for branches, editing, and links.\n\n"
                                                                "🔍 NAVIGATION:\n"
                                                                " • Mouse Wheel: Zoom relative to your cursor.\n"
                                                                " • Right-Click + Drag: Pan the map camera.\n"
                                                                " • Zoom All: Fits all expanded nodes to your current window.\n\n"
                                                                "🔗 RESOURCES:\n"
                                                                " • 🔗 Symbol: Means the node contains a URL or local File link.\n"
                                                                " • Link Website: Right-Click > Resources > Link URL.\n"
                                                                " • Link File: Right-Click > Resources > Link Local File.\n\n"
                                                                "🟠 BADGES:\n"
                                                                " • Orange circle shows the number of hidden children when collapsed."
        )
        messagebox.showinfo("Mind Map Help", help_text)

    # --- COORDINATES ---
    def to_screen(self, wx, wy):
        return (wx * self.zoom_level) + self.offset_x, (wy * self.zoom_level) + self.offset_y

    def to_world(self, sx, sy):
        return (sx - self.offset_x) / self.zoom_level, (sy - self.offset_y) / self.zoom_level

    # --- NAVIGATION ---
    def on_zoom(self, event):
        old_zoom = self.zoom_level
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_level = max(0.05, min(self.zoom_level * factor, 10.0))
        mx, my = event.x, event.y
        self.offset_x = mx - (mx - self.offset_x) * (self.zoom_level / old_zoom)
        self.offset_y = my - (my - self.offset_y) * (self.zoom_level / old_zoom)
        self.redraw()

    def do_pan(self, event):
        if self.last_mouse_x != 0:
            self.offset_x += (event.x - self.last_mouse_x)
            self.offset_y += (event.y - self.last_mouse_y)
        self.last_mouse_x, self.last_mouse_y = event.x, event.y
        self.redraw()

    def zoom_all(self):
        if not self.nodes: return
        all_coords = []

        def collect(nid):
            all_coords.append(self.nodes[nid]["pos"])
            if self.nodes[nid].get("expanded", True):
                for cid in self.nodes[nid]["children"]: collect(cid)

        collect(self.root_id)
        ax, ay = [p[0] for p in all_coords], [p[1] for p in all_coords]
        min_x, max_x, min_y, max_y = min(ax) - 60, max(ax) + 60, min(ay) - 30, max(ay) + 30
        mw, mh = max(1, max_x - min_x), max(1, max_y - min_y)
        ww, wh = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        self.zoom_level = min(ww / mw, wh / mh, 1.5)
        self.offset_x, self.offset_y = (ww / 2) - ((min_x + max_x) / 2) * self.zoom_level, (wh / 2) - (
                    (min_y + max_y) / 2) * self.zoom_level
        self.redraw()

    # --- INTERACTION ---
    def find_node_at(self, x, y):
        wx, wy = self.to_world(x, y)
        for nid, node in self.nodes.items():
            nx, ny = node["pos"]
            if nx - 75 < wx < nx + 75 and ny - 20 < wy < ny + 20: return nid
        return None

    def on_left_click(self, event):
        self.last_mouse_x, self.last_mouse_y = 0, 0
        self.selected = self.find_node_at(event.x, event.y)
        self.dragging = self.selected
        if self.selected and "link" in self.nodes[self.selected]:
            self.status_var.set(f"Link: {self.nodes[self.selected]['link']}")
        else:
            self.status_var.set("Ready")

    def on_double_click(self, event):
        nid = self.find_node_at(event.x, event.y)
        if nid:
            node = self.nodes[nid]
            if node.get("link"):
                self.open_resource(node["link"])
            elif node["children"]:
                node["expanded"] = not node.get("expanded", True)
                self.redraw()
            else:
                self.edit_node_text(nid)

    def on_right_click(self, event):
        self.last_mouse_x, self.last_mouse_y = event.x, event.y
        self.selected = self.find_node_at(event.x, event.y)
        menu = Menu(self.root, tearoff=0)
        if self.selected:
            menu.add_command(label="Edit Text", command=lambda: self.edit_node_text(self.selected))
            res_menu = Menu(menu, tearoff=0)
            res_menu.add_command(label="Link Website (URL)", command=self.add_url_link)
            res_menu.add_command(label="Link Local File", command=self.add_file_link)
            if self.nodes[self.selected].get("link"):
                res_menu.add_separator()
                res_menu.add_command(label="Remove Link", command=self.remove_link)
            menu.add_cascade(label="Resources", menu=res_menu)
            menu.add_separator()
            menu.add_command(label="Add Branch", command=self.add_branch)
            menu.add_command(label="Delete Node", command=self.delete_node, foreground="red")
        else:
            menu.add_command(label="Zoom All", command=self.zoom_all)
        menu.post(event.x_root, event.y_root)

    # --- LOGIC ---
    def add_url_link(self):
        url = simpledialog.askstring("URL", "Enter Address:")
        if url: self.nodes[self.selected]["link"] = url; self.redraw()

    def add_file_link(self):
        path = filedialog.askopenfilename()
        if path: self.nodes[self.selected]["link"] = path; self.redraw()

    def remove_link(self):
        if self.selected and "link" in self.nodes[self.selected]:
            del self.nodes[self.selected]["link"];
            self.redraw()

    def open_resource(self, path):
        try:
            if path.startswith("http"):
                webbrowser.open(path)
            else:
                if platform.system() == "Windows":
                    os.startfile(path)
                elif platform.system() == "Darwin":
                    subprocess.call(["open", path])
                else:
                    subprocess.call(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def edit_node_text(self, nid):
        new = simpledialog.askstring("Edit", "Text:", initialvalue=self.nodes[nid]["text"])
        if new: self.nodes[nid]["text"] = new; self.redraw()

    def add_branch(self):
        if not self.selected: return
        name = simpledialog.askstring("New", "Name:")
        if not name: return
        cid = f"n_{len(self.nodes)}_{int(self.root.after_get('')) % 1000}"
        px, py = self.nodes[self.selected]["pos"]
        self.nodes[cid] = {"text": name, "children": [], "pos": (px + 200, py), "expanded": True}
        self.nodes[self.selected]["children"].append(cid);
        self.redraw()

    def delete_node(self):
        if self.selected == self.root_id: return
        for n in self.nodes.values():
            if self.selected in n["children"]: n["children"].remove(self.selected)
        del self.nodes[self.selected];
        self.selected = None;
        self.redraw()

    def on_drag(self, event):
        if self.dragging: self.nodes[self.dragging]["pos"] = self.to_world(event.x, event.y); self.redraw()

    # --- DRAWING ---
    def redraw(self):
        self.canvas.delete("all")
        for i in range(-10, 20):
            gx, _ = self.to_screen(i * 150, 0);
            _, gy = self.to_screen(0, i * 150)
            self.canvas.create_line(gx, 0, gx, 2000, fill="#f9f9fb");
            self.canvas.create_line(0, gy, 2000, gy, fill="#f9f9fb")

        def draw_tree(nid, depth=0):
            node = self.nodes[nid]
            sx, sy = self.to_screen(*node["pos"])
            is_exp = node.get("expanded", True)
            if is_exp:
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
                                    font=("Segoe UI", max(4, int(10 * self.zoom_level)), "bold"))
            if node.get("link"): self.canvas.create_text(sx - px + 10, sy, text="🔗",
                                                         font=("Segoe UI", max(4, int(8 * self.zoom_level))))
            if not is_exp and node["children"]:
                bx, by, br = sx + px, sy - py, max(6, int(8 * self.zoom_level))
                self.canvas.create_oval(bx - br, by - br, bx + br, by + br, fill="#f0932b", outline="white")
                self.canvas.create_text(bx, by, text=str(len(node["children"])), fill="white",
                                        font=("Segoe UI", max(4, int(7 * self.zoom_level)), "bold"))

        draw_tree(self.root_id)

    def expand_all(self):
        for n in self.nodes.values(): n["expanded"] = True
        self.redraw()

    def collapse_all(self):
        for nid, n in self.nodes.items():
            if nid != self.root_id: n["expanded"] = False
        self.redraw()

    def save_project(self):
        with open(os.path.join(self.projects_dir, self.current_project), "w") as f: json.dump(self.nodes, f, indent=2)
        messagebox.showinfo("Saved", "Project saved!")

    def load_project(self):
        path = os.path.join(self.projects_dir, self.current_project)
        if os.path.exists(path):
            with open(path, "r") as f:
                self.nodes = json.load(f)
        else:
            self.nodes = {self.root_id: {"text": "Central Idea", "children": [], "pos": (0, 0), "expanded": True}}
        self.redraw()


if __name__ == "__main__":
    root = tk.Tk()
    app = MindMapApp(root)
    root.mainloop()