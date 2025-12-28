import tkinter as tk
from tkinter import simpledialog, messagebox, Menu, filedialog, ttk, colorchooser
import json
import os
import webbrowser
import platform
import subprocess


# --- NOTE DIALOG CLASS ---
class NoteDialog(tk.Toplevel):
    def __init__(self, parent, initial_data=None):
        super().__init__(parent)
        self.title("Note Editor")
        self.geometry("500x500")
        self.result = None

        # Make this window modal
        self.transient(parent)
        self.grab_set()

        # FIX: Ensure closing the window via the "X" button also saves the data
        self.protocol("WM_DELETE_WINDOW", self.save_and_close)

        # Toolbar
        self.toolbar = tk.Frame(self, bg="#f0f0f0")
        self.toolbar.pack(side="top", fill="x")

        tk.Button(self.toolbar, text="B", font=("Segoe UI", 9, "bold"), width=3,
                  command=self.toggle_bold).pack(side="left", padx=2, pady=2)
        tk.Button(self.toolbar, text="Color", command=self.choose_color).pack(side="left", padx=2)
        tk.Button(self.toolbar, text="• List", command=self.add_bullet).pack(side="left", padx=2)

        tk.Label(self, text="Title:").pack(anchor="w", padx=10, pady=(10, 0))
        self.title_var = tk.StringVar(value=initial_data.get("title", "New Note") if initial_data else "New Note")
        tk.Entry(self, textvariable=self.title_var, font=("Segoe UI", 11)).pack(fill="x", padx=10, pady=5)

        tk.Label(self, text="Note content:").pack(anchor="w", padx=10)
        self.text_area = tk.Text(self, font=("Segoe UI", 10), undo=True)
        self.text_area.pack(fill="both", expand=True, padx=10, pady=5)

        if initial_data:
            self.text_area.insert("1.0", initial_data.get("content", ""))

        # Save Button
        tk.Button(self, text="Save Note", bg="#2ecc71", fg="white", font=("Segoe UI", 10, "bold"),
                  command=self.save_and_close).pack(pady=10)

    def toggle_bold(self):
        try:
            self.text_area.tag_configure("bold", font=("Segoe UI", 10, "bold"))
            current_tags = self.text_area.tag_names("sel.first")
            if "bold" in current_tags:
                self.text_area.tag_remove("bold", "sel.first", "sel.last")
            else:
                self.text_area.tag_add("bold", "sel.first", "sel.last")
        except tk.TclError:
            pass

    def choose_color(self):
        color = colorchooser.askcolor()[1]
        if color:
            tag_name = f"color_{color}"
            self.text_area.tag_configure(tag_name, foreground=color)
            try:
                self.text_area.tag_add(tag_name, "sel.first", "sel.last")
            except tk.TclError:
                pass

    def add_bullet(self):
        self.text_area.insert("insert", "\n• ")

    def save_and_close(self):
        # Captures the data into the result variable before destruction
        self.result = {
            "type": "note",
            "title": self.title_var.get().strip() or "Untitled Note",
            "content": self.text_area.get("1.0", "end-1c")
        }
        self.destroy()


# --- TOOLTIP CLASS ---
class NodeTooltip:
    def __init__(self, canvas):
        self.canvas = canvas
        self.tip_window = None
        self.id = None

    def show(self, text, x, y):
        if self.tip_window or not text:
            return
        x += 20
        y += 20
        self.tip_window = tw = tk.Toplevel(self.canvas)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{int(x)}+{int(y)}")
        tw.attributes("-topmost", True)
        label = tk.Label(tw, text=text, justify="left",
                         background="#2c3e50", foreground="white", relief="flat", borderwidth=1,
                         font=("Segoe UI", 9), padx=8, pady=5)
        label.pack()

    def hide(self):
        tw = self.tip_window
        self.tip_window = None
        if tw: tw.destroy()


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

        self.load_project()
        self.root.after(500, self.reorganize_and_zoom)

    # --- HOVER LOGIC ---
    def on_mouse_move(self, e):
        nid = self.find_node_at(e.x, e.y)
        if nid != self.last_hover_node:
            self.cancel_hover()
            self.tooltip.hide()
            self.last_hover_node = nid
            if nid:
                self.hover_after_id = self.root.after(750, lambda: self.show_node_details(nid, e.x_root, e.y_root))

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
                name = l['title'] if isinstance(l, dict) else os.path.basename(str(l))
                details.append(f"• {name}")
        self.tooltip.show("\n".join(details), root_x, root_y)

    # --- AUTO-LAYOUT LOGIC ---
    def reorganize_nodes(self):
        if not self.nodes: return
        self.next_y = 0
        v_gap, h_gap = 80, 220

        def layout_recursive(nid, depth):
            node = self.nodes[nid]
            x_pos = depth * h_gap
            if not node.get("expanded", True) or not node["children"]:
                y_pos = self.next_y
                node["pos"] = [x_pos, y_pos]
                self.next_y += v_gap
                return y_pos
            child_ys = [layout_recursive(cid, depth + 1) for cid in node["children"] if cid in self.nodes]
            actual_y = (child_ys[0] + child_ys[-1]) / 2 if child_ys else self.next_y
            node["pos"] = [x_pos, actual_y]
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
            px = 75
            if (nx + px - 15) < wx < (nx + px + 15) and (ny - 15) < wy < (ny + 15):
                self.selected = clicked_node
                self.add_branch()
                return
            self.selected = clicked_node
            self.dragging = self.selected
        else:
            self.drag_box_start = (e.x, e.y)

    def is_descendant(self, parent_id, child_id):
        if child_id in self.nodes[parent_id]["children"]: return True
        for sub_child in self.nodes[parent_id]["children"]:
            if self.is_descendant(sub_child, child_id): return True
        return False

    def on_drag(self, e):
        self.cancel_hover()
        self.tooltip.hide()
        if self.dragging:
            self.nodes[self.dragging]["pos"] = self.to_world(e.x, e.y)
            target = self.find_node_at(e.x, e.y)
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
                for pid, node in self.nodes.items():
                    if self.dragging in node["children"]:
                        node["children"].remove(self.dragging)
                        break
                self.nodes[self.drop_target]["children"].append(self.dragging)
                self.reorganize_and_zoom()
            self.save_project()
            self.dragging = None;
            self.drop_target = None;
            self.redraw()
        if self.drag_box_start:
            x0, y0 = self.drag_box_start
            if e.x < x0 or e.y < y0:
                if abs(e.x - x0) > 10: self.zoom_all()
            elif abs(e.x - x0) > 10 and abs(e.y - y0) > 10:
                self.box_zoom(x0, y0, e.x, e.y)
            self.drag_box_start = None;
            self.redraw()

    def box_zoom(self, x0, y0, x1, y1):
        wx0, wy0 = self.to_world(x0, y0);
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
        self.offset_x += (e.x - self.pan_last_x);
        self.offset_y += (e.y - self.pan_last_y)
        self.pan_last_x, self.pan_last_y = e.x, e.y;
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
                        self.canvas.create_line(sx, sy, (sx + cx) / 2, sy, (sx + cx) / 2, cy, cx, cy, smooth=True,
                                                fill="#dcdde1", width=max(1, int(2 * self.zoom_level)))
                        draw_tree(cid, depth + 1)
            px, py = 75 * self.zoom_level, 20 * self.zoom_level
            color = ["#4834d4", "#686de0", "#eb4d4b", "#6ab04c"][depth % 4]
            bw = 4 if nid == self.drop_target else max(1, int(2 * self.zoom_level))
            dash = (5, 5) if nid == self.drop_target else None
            self.canvas.create_rectangle(sx - px, sy - py, sx + px, sy + py, fill="white", outline=color, width=bw,
                                         dash=dash)
            self.canvas.create_text(sx, sy, text=node["text"],
                                    font=("Segoe UI", max(5, int(10 * self.zoom_level)), "bold"))
            br = 8 * self.zoom_level
            self.canvas.create_oval(sx + px - br, sy - br, sx + px + br, sy + br, fill="white", outline=color)
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
        v = []

        def col(nid):
            v.append(self.nodes[nid]["pos"])
            if self.nodes[nid].get("expanded", True):
                for cid in self.nodes[nid]["children"]: col(cid)

        col(self.root_id)
        ax = [p[0] for p in v];
        ay = [p[1] for p in v]
        min_wx, max_wx, min_wy, max_wy = min(ax) - 100, max(ax) + 100, min(ay) - 60, max(ay) + 60
        sw, sh = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        self.zoom_level = min(sw / max(max_wx - min_wx, 1), sh / max(max_wy - min_wy, 1), 1.5)
        self.offset_x = (sw / 2) - ((min_wx + max_wx) / 2) * self.zoom_level
        self.offset_y = (sh / 2) - ((min_wy + max_wy) / 2) * self.zoom_level
        self.redraw()

    def show_help(self):
        h = "Mind Map Pro Help:\n- RESOURCES: Add URLs, Files, or Rich Text Notes.\n- HOVER: See resource details.\n- DRAG: Re-parent nodes."
        messagebox.showinfo("Help", h)

    def load_settings(self):
        if os.path.exists(self.settings_path):
            with open(self.settings_path, "r") as f: return json.load(f)
        return {"last_project": "central.json", "recent": []}

    def save_settings(self):
        with open(self.settings_path, "w") as f: json.dump(self.settings, f, indent=2)

    def update_recent_list(self, filename):
        r = self.settings.get("recent", [])
        if filename in r: r.remove(filename)
        r.insert(0, filename)
        self.settings["recent"], self.settings["last_project"] = r[:5], filename
        self.save_settings();
        self.update_recent_menu()

    def update_recent_menu(self):
        self.recent_menu.delete(0, "end")
        for f in self.settings.get("recent", []):
            self.recent_menu.add_command(label=f, command=lambda f=f: self.switch_project(f))

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
        if path: self.current_project = os.path.basename(path); self.save_project(); self.update_recent_list(
            self.current_project); self.update_title()

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
        self.tooltip.hide();
        self.pan_last_x, self.pan_last_y = e.x, e.y;
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
        self.tooltip.hide();
        nid = self.find_node_at(e.x, e.y)
        if nid:
            if self.nodes[nid].get("links"):
                self.manage_resources(nid)
            elif self.nodes[nid]["children"]:
                self.nodes[nid]["expanded"] = not self.nodes[nid].get("expanded", True); self.reorganize_and_zoom()
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
        tree.heading("Path", text="Path / URL / Title")
        tree.column("Type", width=80);
        tree.column("Path", width=470)
        tree.pack(side="left", fill="both", expand=True)
        vs = tk.Scrollbar(f, command=tree.yview);
        vs.pack(side="right", fill="y");
        tree.config(yscrollcommand=vs.set)

        def refresh():
            for i in tree.get_children(): tree.delete(i)
            for idx, l in enumerate(node.get("links", [])):
                if isinstance(l, dict) and l.get("type") == "note":
                    tree.insert("", "end", values=("📝 Note", l.get("title", "Untitled")), iid=str(idx))
                else:
                    r_type = "🌐 Web" if str(l).startswith("http") else "📄 File"
                    tree.insert("", "end", values=(r_type, l), iid=str(idx))

        def open_selected(e=None):
            sel = tree.selection()
            if not sel: return
            idx = int(sel[0]);
            item = node["links"][idx]
            if isinstance(item, dict) and item.get("type") == "note":
                dialog = NoteDialog(manager, initial_data=item)
                manager.wait_window(dialog)
                if dialog.result:
                    node["links"][idx] = dialog.result
                    self.save_project();
                    refresh()
            else:
                webbrowser.open(item)

        tree.bind("<Double-1>", open_selected)
        btn_f = tk.Frame(manager);
        btn_f.pack(fill="x", pady=10, padx=10)

        tk.Button(btn_f, text="+ URL", command=lambda: [
            (u := simpledialog.askstring("URL", "Address:")) and node["links"].append(u),
            refresh(), self.save_project(), self.redraw()]).pack(side="left", padx=2)

        tk.Button(btn_f, text="+ File", command=lambda: [
            (f := filedialog.askopenfilename()) and node["links"].append(f),
            refresh(), self.save_project(), self.redraw()]).pack(side="left", padx=2)

        def add_note_ui():
            d = NoteDialog(manager)
            manager.wait_window(d)
            if d.result:
                node["links"].append(d.result)
                self.save_project()
                refresh();
                self.redraw()

        tk.Button(btn_f, text="+ Note", bg="#d1d8ff", command=add_note_ui).pack(side="left", padx=2)

        tk.Button(btn_f, text="Delete", fg="red", command=lambda: [
            node["links"].pop(int(tree.selection()[0])) if tree.selection() else None,
            refresh(), self.save_project(), self.redraw()]).pack(side="right")
        refresh()

    def edit_node_text(self, nid):
        new = simpledialog.askstring("Edit", "Text:", initialvalue=self.nodes[nid]["text"])
        if new: self.nodes[nid]["text"] = new; self.save_project(); self.redraw()

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