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
        self.root.title("Mind Map Pro - Resource Focused")
        self.root.geometry("1400x900")

        # --- UI LAYOUT ---
        self.toolbar = tk.Frame(self.root, bg="#f5f5f7")
        self.toolbar.pack(fill="x", side="top")

        tk.Button(self.toolbar, text="Zoom All", command=self.zoom_all, bg="#d1d8ff").pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Expand All", command=self.expand_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Collapse All", command=self.collapse_all).pack(side="left", padx=5, pady=3)
        tk.Button(self.toolbar, text="Help", command=self.show_help).pack(side="right", padx=10, pady=3)

        self.status_var = tk.StringVar(value="All changes auto-saved")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief="sunken", anchor="w",
                                   bg="#f0f0f0")
        self.status_bar.pack(side="bottom", fill="x")

        # --- CANVAS WITH SCROLLBARS ---
        self.canvas_frame = tk.Frame(self.root)
        self.canvas_frame.pack(fill="both", expand=True)

        self.h_scroll = tk.Scrollbar(self.canvas_frame, orient="horizontal")
        self.h_scroll.pack(side="bottom", fill="x")
        self.v_scroll = tk.Scrollbar(self.canvas_frame, orient="vertical")
        self.v_scroll.pack(side="right", fill="y")

        self.canvas = tk.Canvas(self.canvas_frame, bg="white", highlightthickness=0,
                                xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.config(command=self.canvas.yview)

        # --- STATE ---
        self.zoom_level = 1.0
        self.offset_x, self.offset_y = 700, 450
        self.pan_start_x, self.pan_start_y = 0, 0
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
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        # Robust Right-Click Logic: Menu on Press, Pan on Motion
        self.canvas.bind("<Button-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.do_pan)

        self.canvas.bind("<MouseWheel>", self.on_mouse_scroll_v)
        self.canvas.bind("<Shift-MouseWheel>", self.on_mouse_scroll_h)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        self.load_project()
        self.root.after(100, self.zoom_all)

    def show_help(self):
        help_text = (
                "🚀 UPDATED CONTROLS\n" + "=" * 40 + "\n"
                                                    "🖱️ RIGHT-CLICK: Opens the menu immediately.\n"
                                                    "🖱️ RIGHT-CLICK + DRAG: Pans the camera view.\n"
                                                    "🖱️ SCROLL: Vertical (Wheel), Horizontal (Shift+Wheel).\n"
                                                    "🔗 LINKS: Double-click nodes with icon to manage.\n"
                                                    "📋 COPY: Use 'Copy Link' in the Resource Manager."
        )
        messagebox.showinfo("Mind Map Help", help_text)

    # --- COORDINATES ---
    def to_screen(self, wx, wy):
        return (wx * self.zoom_level) + self.offset_x, (wy * self.zoom_level) + self.offset_y

    def to_world(self, sx, sy):
        cx = self.canvas.canvasx(sx)
        cy = self.canvas.canvasy(sy)
        return (cx - self.offset_x) / self.zoom_level, (cy - self.offset_y) / self.zoom_level

    # --- NAVIGATION & PANNING ---
    def update_scroll_region(self):
        if not self.nodes: return
        all_screen_coords = [self.to_screen(n["pos"][0], n["pos"][1]) for n in self.nodes.values()]
        xs = [p[0] for p in all_screen_coords]
        ys = [p[1] for p in all_screen_coords]
        pad = 1000
        self.canvas.config(scrollregion=(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad))

    def on_mouse_scroll_v(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_mouse_scroll_h(self, event):
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_right_press(self, event):
        # Start pan tracking
        self.pan_start_x, self.pan_start_y = event.x, event.y
        self.canvas.scan_mark(event.x, event.y)
        # Show menu immediately on click
        self.show_right_click_menu(event)

    def do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.redraw()

    def zoom_all(self):
        if not self.nodes: return
        all_coords = [n["pos"] for n in self.nodes.values()]
        ax, ay = [p[0] for p in all_coords], [p[1] for p in all_coords]
        min_x, max_x, min_y, max_y = min(ax) - 80, max(ax) + 80, min(ay) - 40, max(ay) + 40
        mw, mh = max(1, max_x - min_x), max(1, max_y - min_y)
        ww, wh = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        self.zoom_level = min(ww / mw, wh / mh, 1.5)
        self.offset_x, self.offset_y = (ww / 2) - ((min_x + max_x) / 2) * self.zoom_level, (wh / 2) - (
                (min_y + max_y) / 2) * self.zoom_level
        self.redraw()

    # --- INTERACTION ---
    def on_left_click(self, event):
        self.selected = self.find_node_at(event.x, event.y)
        self.dragging = self.selected

    def on_release(self, event):
        if self.dragging:
            self.save_project(silent=True)
            self.dragging = None

    def on_double_click(self, event):
        nid = self.find_node_at(event.x, event.y)
        if nid:
            node = self.nodes[nid]
            if node.get("links"):
                self.manage_resources(nid)
            elif node["children"]:
                node["expanded"] = not node.get("expanded", True)
                self.redraw()
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
            # 1. PLACE MANAGE RESOURCES FIRST
            menu.add_command(label="Manage Resources...", command=lambda: self.manage_resources(self.selected))
            menu.add_separator()
            menu.add_command(label="Edit Text", command=lambda: self.edit_node_text(self.selected))

            res_menu = Menu(menu, tearoff=0)
            res_menu.add_command(label="Add URL", command=self.add_url_link)
            res_menu.add_command(label="Add File", command=self.add_file_link)
            menu.add_cascade(label="Add New Resource", menu=res_menu)

            menu.add_separator()
            menu.add_command(label="Add Branch", command=self.add_branch)
            menu.add_command(label="Delete Node", command=self.delete_node, foreground="red")
        else:
            menu.add_command(label="Zoom All", command=self.zoom_all)
        menu.post(event.x_root, event.y_root)

    # --- RESOURCE MANAGEMENT ---
    def manage_resources(self, nid):
        node = self.nodes[nid]
        manager = tk.Toplevel(self.root)
        manager.title(f"Resources: {node['text']}")
        manager.geometry("650x450")

        list_frame = tk.Frame(manager)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)

        h_scroll = tk.Scrollbar(list_frame, orient="horizontal")
        h_scroll.pack(side="bottom", fill="x")
        v_scroll = tk.Scrollbar(list_frame, orient="vertical")
        v_scroll.pack(side="right", fill="y")

        columns = ("#1", "#2")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                            yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        tree.heading("#1", text="Type")
        tree.heading("#2", text="Path / URL")
        tree.column("#1", width=70, minwidth=70)
        tree.column("#2", width=1200, minwidth=400)
        tree.pack(side="left", fill="both", expand=True)

        v_scroll.config(command=tree.yview)
        h_scroll.config(command=tree.xview)

        def refresh_tree():
            for i in tree.get_children(): tree.delete(i)
            for idx, link in enumerate(node.get("links", [])):
                l_type = "Web" if link.startswith("http") else "File"
                tree.insert("", "end", iid=idx, values=(l_type, link))

        def open_sel():
            sel = tree.selection()
            if sel: self.open_resource(node["links"][int(sel[0])])

        # COPY LINK FUNCTION
        def copy_sel():
            sel = tree.selection()
            if sel:
                link_text = node["links"][int(sel[0])]
                self.root.clipboard_clear()
                self.root.clipboard_append(link_text)
                self.status_var.set("Link copied to clipboard")

        def delete_sel():
            sel = tree.selection()
            if sel:
                del node["links"][int(sel[0])]
                refresh_tree();
                self.save_project(silent=True);
                self.redraw()

        btn_frame = tk.Frame(manager)
        btn_frame.pack(fill="x", pady=5, padx=10)
        tk.Button(btn_frame, text="Open Selected", command=open_sel).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Copy Link", command=copy_sel).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Delete Selected", command=delete_sel, fg="red").pack(side="right", padx=5)
        refresh_tree()

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
        if new: self.nodes[nid]["text"] = new; self.save_project(silent=True); self.redraw()

    def add_url_link(self):
        url = simpledialog.askstring("URL", "Enter Address:")
        if url:
            if "links" not in self.nodes[self.selected]: self.nodes[self.selected]["links"] = []
            self.nodes[self.selected]["links"].append(url)
            self.save_project(silent=True);
            self.redraw()

    def add_file_link(self):
        path = filedialog.askopenfilename()
        if path:
            if "links" not in self.nodes[self.selected]: self.nodes[self.selected]["links"] = []
            self.nodes[self.selected]["links"].append(path)
            self.save_project(silent=True);
            self.redraw()

    def add_branch(self):
        if not self.selected: return
        name = simpledialog.askstring("New", "Name:")
        if not name: return
        cid = f"n_{len(self.nodes)}_{int(self.root.after_get('')) % 1000}"
        px, py = self.nodes[self.selected]["pos"]
        self.nodes[cid] = {"text": name, "children": [], "pos": (px + 200, py), "expanded": True, "links": []}
        self.nodes[self.selected]["children"].append(cid)
        self.save_project(silent=True);
        self.redraw()

    def delete_node(self):
        if self.selected == self.root_id: return
        for n in self.nodes.values():
            if self.selected in n["children"]: n["children"].remove(self.selected)
        del self.nodes[self.selected]
        self.selected = None;
        self.save_project(silent=True);
        self.redraw()

    def on_drag(self, event):
        if self.dragging:
            self.nodes[self.dragging]["pos"] = self.to_world(event.x, event.y)
            self.redraw()

    def on_release(self, event):
        if self.dragging:
            self.save_project(silent=True)
            self.dragging = None

    def redraw(self):
        self.canvas.delete("all")
        for i in range(-15, 25):
            gx, _ = self.to_screen(i * 150, 0)
            _, gy = self.to_screen(0, i * 150)
            self.canvas.create_line(gx, -5000, gx, 5000, fill="#f9f9fb")
            self.canvas.create_line(-5000, gy, 5000, gy, fill="#f9f9fb")

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

            links = node.get("links", [])
            if links:
                l_text = "🔗" if len(links) == 1 else f"🔗{len(links)}"
                self.canvas.create_text(sx - px + 15, sy, text=l_text,
                                        font=("Segoe UI", max(4, int(8 * self.zoom_level))))

        draw_tree(self.root_id)
        self.update_scroll_region()

    def expand_all(self):
        for n in self.nodes.values(): n["expanded"] = True
        self.redraw()

    def collapse_all(self):
        for nid, n in self.nodes.items():
            if nid != self.root_id: n["expanded"] = False
        self.redraw()

    def save_project(self, silent=False):
        try:
            with open(os.path.join(self.projects_dir, self.current_project), "w") as f:
                json.dump(self.nodes, f, indent=2)
            self.status_var.set("All changes auto-saved")
        except Exception as e:
            self.status_var.set(f"Save Error: {e}")

    def load_project(self):
        path = os.path.join(self.projects_dir, self.current_project)
        if os.path.exists(path):
            with open(path, "r") as f:
                self.nodes = json.load(f)
                for n in self.nodes.values():
                    if "links" not in n: n["links"] = []
        else:
            self.nodes = {
                self.root_id: {"text": "Central Idea", "children": [], "pos": (0, 0), "expanded": True, "links": []}}
        self.redraw()


if __name__ == "__main__":
    root = tk.Tk()
    app = MindMapApp(root)
    root.mainloop()