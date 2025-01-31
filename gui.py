import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from models import Node, Router, Cable, Connection, TrafficMatrix
from logic import (
    calculate_all_shortest_paths,
    compute_flows_on_connections,
    save_data_to_file,
    load_data_from_file,
    find_min_router_per_node,
    find_min_cable,
    sum_router_costs,
    sum_cable_costs
)

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Network Management App")

        # Параметры Canvas
        self.canvas_width = 800
        self.canvas_height = 600
        self.center_x = self.canvas_width // 2
        self.center_y = self.canvas_height // 2
        self.SCALE = 4.0

        # Основные данные
        self.routers = []
        self.nodes = []
        self.connections = []
        self.traffic_matrix = TrafficMatrix()
        self.cables = []

        # Глобальный packet_size
        self.global_packet_size = 128.0

        # Пример начальных данных
        default_router = Router("testNode", 9999999, 100)
        self.routers.append(default_router)
        self.cables.append(Cable("DefaultCable", 1.0, 1000))
        self.cables.append(Cable("HighSpeedCable", 2.0, 10000))

        # ---------- Интерфейс ----------
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Добавить узел", command=self.add_node_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Добавить соединение", command=self.add_connection_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Матрица нагрузки", command=self.show_traffic_matrix_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Потоки на каналах", command=self.show_data_flows_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Кратчайшие пути", command=self.show_shortest_paths_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Показать узлы", command=self.show_nodes_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Показать соединения", command=self.show_connections_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Мин. роутер/кабель", command=self.compute_min_resources).pack(side=tk.LEFT, padx=5)

        # Новая кнопка «Полносвязный граф»
        ttk.Button(btn_frame, text="Полносвязный граф", command=self.make_complete_graph).pack(side=tk.LEFT, padx=5)

        # Кнопка Packet Size
        ttk.Button(btn_frame, text="Packet Size", command=self.show_packet_size_dialog).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Сохранить", command=self.save_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Загрузить", command=self.load_data).pack(side=tk.LEFT, padx=5)

        # Canvas
        self.canvas = tk.Canvas(main_frame, bg="white", width=self.canvas_width, height=self.canvas_height)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Нижняя панель: масштаб
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        tk.Label(bottom_frame, text="Масштаб:").pack(side=tk.LEFT, padx=5)
        self.scale_entry = tk.Entry(bottom_frame, width=10)
        self.scale_entry.insert(0, str(self.SCALE))
        self.scale_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="Применить", command=self.apply_scale).pack(side=tk.LEFT, padx=5)

        self.draw_centered_grid()

    # --------------------------------------------------------------------------
    # Новый метод: сделать полносвязный граф
    def make_complete_graph(self):
        if len(self.nodes) < 2:
            messagebox.showinfo("Полносвязный граф", "Недостаточно узлов для полносвязной сети.")
            return

        if not self.cables:
            messagebox.showinfo("Полносвязный граф", "Нет ни одного кабеля! Добавьте кабель.")
            return

        # Возьмём, к примеру, первый кабель из списка (или любой другой)
        cable_for_all = self.cables[0]

        # Создадим множество "frozenset({node1, node2})" для уже существующих соединений
        existing_pairs = set()
        for c in self.connections:
            pair = frozenset([c.node1, c.node2])
            existing_pairs.add(pair)

        # Перебираем все пары узлов
        new_count = 0
        for i in range(len(self.nodes)):
            for j in range(i+1, len(self.nodes)):
                n1 = self.nodes[i]
                n2 = self.nodes[j]
                pair = frozenset([n1, n2])
                if pair not in existing_pairs:
                    # Создаём новое соединение
                    conn_name = f"auto_{n1.name}_{n2.name}"
                    new_conn = Connection(conn_name, n1, n2, cable_for_all)
                    self.connections.append(new_conn)
                    new_count += 1

        self.draw_centered_grid()
        messagebox.showinfo("Полносвязный граф",
                            f"Добавлено {new_count} новых соединений (использован кабель '{cable_for_all.cable_name}').")
    # --------------------------------------------------------------------------
    # Диалог для изменения глобального packet_size
    def show_packet_size_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Глобальный Packet Size")

        tk.Label(dialog, text="Packet Size:").pack(padx=10, pady=10)
        entry = tk.Entry(dialog)
        entry.insert(0, str(self.global_packet_size))
        entry.pack(padx=10, pady=5)

        def on_confirm():
            try:
                val = float(entry.get())
                if val <= 0:
                    raise ValueError
                self.global_packet_size = val
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректное значение Packet Size (> 0).")

        ttk.Button(dialog, text="OK", command=on_confirm).pack(pady=10)

    # --------------------------------------------------------------------------
    # Рисование на Canvas

    def draw_centered_grid(self, step=50):
        """Очищаем Canvas, рисуем сетку + оси и отрисовываем все узлы/соединения."""
        self.canvas.delete("all")

        # Координатная сетка
        for x in range(0, self.canvas_width, step):
            self.canvas.create_line(x, 0, x, self.canvas_height, fill="lightgray")
        for y in range(0, self.canvas_height, step):
            self.canvas.create_line(0, y, self.canvas_width, y, fill="lightgray")

        # «Красные оси»
        self.canvas.create_line(self.center_x, 0, self.center_x, self.canvas_height, fill="red")
        self.canvas.create_line(0, self.center_y, self.canvas_width, self.center_y, fill="red")

        self.redraw_all()

    def logic_to_canvas_coords(self, x: float, y: float):
        """Преобразуем логические координаты (x,y) в координаты Canvas (cx, cy)."""
        scaled_x = x * self.SCALE
        scaled_y = y * self.SCALE
        cx = self.center_x + scaled_x
        cy = self.center_y - scaled_y
        return (cx, cy)

    def redraw_all(self):
        """Перерисовываем соединения и узлы."""
        # Сначала линии соединений
        for conn in self.connections:
            x1, y1 = self.logic_to_canvas_coords(conn.node1.x, conn.node1.y)
            x2, y2 = self.logic_to_canvas_coords(conn.node2.x, conn.node2.y)
            self.canvas.create_line(x1, y1, x2, y2, fill="black")

        # Затем узлы поверх
        for node in self.nodes:
            cx, cy = self.logic_to_canvas_coords(node.x, node.y)
            self.canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="blue")
            self.canvas.create_text(cx, cy - 15, text=node.name, fill="black")

    def apply_scale(self):
        """Считываем новый масштаб из поля ввода и перерисовываем."""
        try:
            new_scale = float(self.scale_entry.get())
            if new_scale <= 0:
                raise ValueError
            self.SCALE = new_scale
            self.draw_centered_grid()
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректное значение масштаба (должно быть > 0).")

    # --------------------------------------------------------------------------
    # Добавление узла

    def add_node_dialog(self):
        """Окно диалога для добавления нового узла."""
        dialog = tk.Toplevel(self)
        dialog.title("Добавить узел")

        tk.Label(dialog, text="X (0..1_000_000):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
        x_entry = tk.Entry(dialog)
        x_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(dialog, text="Y (0..1_000_000):").grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
        y_entry = tk.Entry(dialog)
        y_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(dialog, text="Название узла:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.E)
        name_entry = tk.Entry(dialog)
        name_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(dialog, text="Выберите роутер:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.NE)
        router_tree = ttk.Treeview(dialog, columns=("model", "cap", "cost"), show="headings", height=5)
        router_tree.heading("model", text="Модель")
        router_tree.heading("cap", text="Пропускная")
        router_tree.heading("cost", text="Стоимость")
        router_tree.grid(row=3, column=1, padx=5, pady=5)

        for r in self.routers:
            router_tree.insert("", tk.END, values=(r.model_name, r.capacity, r.cost))

        self.selected_router = None

        def on_router_select(event):
            item_id = router_tree.focus()
            if item_id:
                vals = router_tree.item(item_id, "values")
                model_name = vals[0]
                for router in self.routers:
                    if router.model_name == model_name:
                        self.selected_router = router
                        break

        router_tree.bind("<<TreeviewSelect>>", on_router_select)

        def on_add_router():
            sub = tk.Toplevel(dialog)
            sub.title("Добавить роутер")

            tk.Label(sub, text="Модель:").grid(row=0, column=0, padx=5, pady=5)
            m_e = tk.Entry(sub)
            m_e.grid(row=0, column=1, padx=5, pady=5)

            tk.Label(sub, text="Пропускная способность:").grid(row=1, column=0, padx=5, pady=5)
            c_e = tk.Entry(sub)
            c_e.grid(row=1, column=1, padx=5, pady=5)

            tk.Label(sub, text="Стоимость:").grid(row=2, column=0, padx=5, pady=5)
            cost_e = tk.Entry(sub)
            cost_e.grid(row=2, column=1, padx=5, pady=5)

            def confirm():
                try:
                    model = m_e.get().strip()
                    cap = int(c_e.get())
                    cost = float(cost_e.get())
                    new_r = Router(model, cap, cost)
                    self.routers.append(new_r)
                    router_tree.insert("", tk.END, values=(new_r.model_name, new_r.capacity, new_r.cost))
                    sub.destroy()
                except ValueError:
                    messagebox.showerror("Ошибка", "Некорректные данные.")

            ttk.Button(sub, text="OK", command=confirm).grid(row=3, column=0, columnspan=2, pady=5)

        ttk.Button(dialog, text="Добавить роутер", command=on_add_router)\
            .grid(row=4, column=1, padx=5, pady=5, sticky=tk.E)

        def on_confirm():
            try:
                x_val = float(x_entry.get())
                y_val = float(y_entry.get())
                name_val = name_entry.get().strip()
                if not name_val:
                    messagebox.showerror("Ошибка", "Введите название узла.")
                    return
                if self.selected_router is None:
                    messagebox.showerror("Ошибка", "Выберите роутер из списка.")
                    return

                new_node = Node(x_val, y_val, name_val, self.selected_router)
                self.nodes.append(new_node)
                dialog.destroy()
                self.draw_centered_grid()
            except ValueError:
                messagebox.showerror("Ошибка", "Неверные координаты (ожидается число).")

        ttk.Button(dialog, text="Добавить узел", command=on_confirm)\
            .grid(row=5, column=0, columnspan=2, pady=10)

    # --------------------------------------------------------------------------
    # Добавление соединения

    def add_connection_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Добавить соединение")

        tk.Label(dialog, text="Название соединения:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
        conn_name_e = tk.Entry(dialog)
        conn_name_e.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(dialog, text="Узел 1:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
        node_names = [n.name for n in self.nodes]
        node1_var = tk.StringVar(dialog)
        node2_var = tk.StringVar(dialog)

        if node_names:
            node1_var.set(node_names[0])
            node2_var.set(node_names[0])

        node1_menu = ttk.OptionMenu(dialog, node1_var, *node_names)
        node1_menu.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        tk.Label(dialog, text="Узел 2:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.E)
        node2_menu = ttk.OptionMenu(dialog, node2_var, *node_names)
        node2_menu.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        def refresh_nodes():
            n_names = [n.name for n in self.nodes]
            menu1 = node1_menu["menu"]
            menu1.delete(0, "end")
            for name in n_names:
                menu1.add_command(label=name, command=lambda val=name: node1_var.set(val))

            menu2 = node2_menu["menu"]
            menu2.delete(0, "end")
            for name in n_names:
                menu2.add_command(label=name, command=lambda val=name: node2_var.set(val))

            if n_names:
                node1_var.set(n_names[0])
                node2_var.set(n_names[0])

        ttk.Button(dialog, text="Обновить список узлов", command=refresh_nodes)\
            .grid(row=3, column=1, padx=5, pady=5, sticky=tk.E)

        tk.Label(dialog, text="Выберите кабель:").grid(row=4, column=0, padx=5, pady=5, sticky=tk.NE)
        cable_tree = ttk.Treeview(dialog, columns=("name", "cost", "cap"), show="headings", height=5)
        cable_tree.heading("name", text="Кабель")
        cable_tree.heading("cost", text="Стоим/ед")
        cable_tree.heading("cap", text="Пропускная")
        cable_tree.grid(row=4, column=1, padx=5, pady=5)

        for c in self.cables:
            cable_tree.insert("", tk.END, values=(c.cable_name, c.cost_per_unit, c.capacity))

        self.selected_cable = None
        def on_cable_select(event):
            item_id = cable_tree.focus()
            if item_id:
                vals = cable_tree.item(item_id, "values")
                cable_name = vals[0]
                for cab in self.cables:
                    if cab.cable_name == cable_name:
                        self.selected_cable = cab
                        break

        cable_tree.bind("<<TreeviewSelect>>", on_cable_select)

        def on_add_cable():
            sub = tk.Toplevel(dialog)
            sub.title("Добавить кабель")

            tk.Label(sub, text="Название кабеля:").grid(row=0, column=0, padx=5, pady=5)
            name_e = tk.Entry(sub)
            name_e.grid(row=0, column=1, padx=5, pady=5)

            tk.Label(sub, text="Стоимость/ед:").grid(row=1, column=0, padx=5, pady=5)
            cost_e = tk.Entry(sub)
            cost_e.grid(row=1, column=1, padx=5, pady=5)

            tk.Label(sub, text="Проп. способность:").grid(row=2, column=0, padx=5, pady=5)
            cap_e = tk.Entry(sub)
            cap_e.grid(row=2, column=1, padx=5, pady=5)

            def confirm_cable():
                try:
                    c_name = name_e.get().strip()
                    c_cost = float(cost_e.get())
                    c_cap = int(cap_e.get())
                    new_c = Cable(c_name, c_cost, c_cap)
                    self.cables.append(new_c)
                    cable_tree.insert("", tk.END, values=(new_c.cable_name, new_c.cost_per_unit, new_c.capacity))
                    sub.destroy()
                except ValueError:
                    messagebox.showerror("Ошибка", "Некорректные данные кабеля.")

            ttk.Button(sub, text="OK", command=confirm_cable).grid(row=3, column=0, columnspan=2, pady=5)

        ttk.Button(dialog, text="Добавить кабель", command=on_add_cable)\
            .grid(row=5, column=1, padx=5, pady=5, sticky=tk.E)

        def on_confirm():
            conn_name = conn_name_e.get().strip()
            if not conn_name:
                messagebox.showerror("Ошибка", "Введите название соединения.")
                return

            n1_name = node1_var.get()
            n2_name = node2_var.get()
            if n1_name == n2_name:
                messagebox.showerror("Ошибка", "Нельзя соединять узел с самим собой.")
                return

            if self.selected_cable is None:
                messagebox.showerror("Ошибка", "Выберите кабель из списка.")
                return

            node1_obj = next((n for n in self.nodes if n.name == n1_name), None)
            node2_obj = next((n for n in self.nodes if n.name == n2_name), None)
            if not node1_obj or not node2_obj:
                messagebox.showerror("Ошибка", "Указанные узлы не найдены.")
                return

            new_conn = Connection(conn_name, node1_obj, node2_obj, self.selected_cable)
            self.connections.append(new_conn)
            self.draw_centered_grid()
            dialog.destroy()

        ttk.Button(dialog, text="Добавить соединение", command=on_confirm)\
            .grid(row=6, column=0, columnspan=2, pady=10)

    # --------------------------------------------------------------------------
    # Матрица нагрузки

    def show_traffic_matrix_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Матрица нагрузки")

        frame_top = ttk.Frame(dialog)
        frame_top.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("src", "dst", "traffic")
        tree = ttk.Treeview(frame_top, columns=columns, show="headings", height=8)
        for col in columns:
            tree.heading(col, text=col.capitalize())
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(frame_top, orient="vertical", command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        self._fill_traffic_table(tree)

        frame_bottom = ttk.Frame(dialog)
        frame_bottom.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        tk.Label(frame_bottom, text="Источник:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
        src_var = tk.StringVar()
        node_names = [n.name for n in self.nodes]
        if node_names:
            src_var.set(node_names[0])
        src_menu = ttk.OptionMenu(frame_bottom, src_var, *node_names)
        src_menu.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        tk.Label(frame_bottom, text="Приёмник:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
        dst_var = tk.StringVar()
        if node_names:
            dst_var.set(node_names[0])
        dst_menu = ttk.OptionMenu(frame_bottom, dst_var, *node_names)
        dst_menu.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        tk.Label(frame_bottom, text="traffic:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.E)
        t_entry = tk.Entry(frame_bottom)
        t_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        def on_add_record():
            try:
                t_val = float(t_entry.get())
                src_node = src_var.get()
                dst_node = dst_var.get()
                self.traffic_matrix.set_demand(src_node, dst_node, t_val)
                self._refresh_table(tree)
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректное значение traffic.")

        ttk.Button(frame_bottom, text="Добавить запись", command=on_add_record)\
            .grid(row=3, column=0, columnspan=2, pady=5)

        def on_refresh():
            self._refresh_table(tree)

        ttk.Button(frame_bottom, text="Обновить", command=on_refresh)\
            .grid(row=3, column=2, padx=20, pady=5)

    def _fill_traffic_table(self, treeview: ttk.Treeview):
        for (src, dst), traffic in self.traffic_matrix.demands.items():
            treeview.insert("", tk.END, values=(src, dst, traffic))

    def _refresh_table(self, treeview: ttk.Treeview):
        for item in treeview.get_children():
            treeview.delete(item)
        self._fill_traffic_table(treeview)

    # --------------------------------------------------------------------------
    # Показать узлы (с кнопками Edit / Delete)

    def show_nodes_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Список узлов")

        columns = ("name", "x", "y", "router_model", "router_capacity", "router_cost")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", height=10)
        for col in columns:
            tree.heading(col, text=col)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        def fill_nodes():
            for item in tree.get_children():
                tree.delete(item)
            for node in self.nodes:
                vals = (
                    node.name,
                    f"{node.x}",
                    f"{node.y}",
                    node.router.model_name if node.router else "None",
                    f"{node.router.capacity}" if node.router else "0",
                    f"{node.router.cost}" if node.router else "0",
                )
                tree.insert("", tk.END, values=vals)

        fill_nodes()

        # Кнопки Edit / Delete сбоку
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)

        def on_edit_node():
            item_id = tree.focus()
            if not item_id:
                messagebox.showerror("Ошибка", "Выберите узел для редактирования.")
                return
            vals = tree.item(item_id, "values")
            old_name = vals[0]

            node_obj = next((n for n in self.nodes if n.name == old_name), None)
            if not node_obj:
                messagebox.showerror("Ошибка", "Узел не найден.")
                return

            # Открываем диалог для редактирования
            edit_dialog = tk.Toplevel(dialog)
            edit_dialog.title(f"Редактировать узел {old_name}")

            tk.Label(edit_dialog, text="Название:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
            name_e = tk.Entry(edit_dialog)
            name_e.insert(0, node_obj.name)
            name_e.grid(row=0, column=1, padx=5, pady=5)

            tk.Label(edit_dialog, text="X:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
            x_e = tk.Entry(edit_dialog)
            x_e.insert(0, str(node_obj.x))
            x_e.grid(row=1, column=1, padx=5, pady=5)

            tk.Label(edit_dialog, text="Y:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.E)
            y_e = tk.Entry(edit_dialog)
            y_e.insert(0, str(node_obj.y))
            y_e.grid(row=2, column=1, padx=5, pady=5)

            # Выбор роутера
            tk.Label(edit_dialog, text="Роутер:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.E)
            router_combo = ttk.Combobox(edit_dialog, values=[r.model_name for r in self.routers], state="readonly")
            if node_obj.router:
                router_combo.set(node_obj.router.model_name)
            else:
                router_combo.set("")
            router_combo.grid(row=3, column=1, padx=5, pady=5)

            def on_save():
                try:
                    new_name = name_e.get().strip()
                    new_x = float(x_e.get())
                    new_y = float(y_e.get())

                    router_name = router_combo.get()
                    new_router = next((r for r in self.routers if r.model_name == router_name), None)

                    node_obj.name = new_name
                    node_obj.x = new_x
                    node_obj.y = new_y
                    node_obj.router = new_router

                    # Перерисуем
                    fill_nodes()
                    self.draw_centered_grid()
                    edit_dialog.destroy()
                except ValueError:
                    messagebox.showerror("Ошибка", "Некорректные координаты.")

            ttk.Button(edit_dialog, text="Сохранить", command=on_save).grid(row=4, column=0, columnspan=2, pady=10)

        def on_delete_node():
            item_id = tree.focus()
            if not item_id:
                messagebox.showerror("Ошибка", "Выберите узел для удаления.")
                return
            vals = tree.item(item_id, "values")
            node_name = vals[0]
            node_obj = next((n for n in self.nodes if n.name == node_name), None)
            if not node_obj:
                messagebox.showerror("Ошибка", "Узел не найден.")
                return

            # Удаляем все connections, в которых он участвует
            self.connections = [c for c in self.connections if c.node1 != node_obj and c.node2 != node_obj]
            # Удаляем сам узел
            self.nodes.remove(node_obj)

            fill_nodes()
            self.draw_centered_grid()

        ttk.Button(btn_frame, text="Edit", command=on_edit_node).pack(pady=5)
        ttk.Button(btn_frame, text="Delete", command=on_delete_node).pack(pady=5)

    # --------------------------------------------------------------------------
    # Показать соединения (с кнопками Edit / Delete)

    def show_connections_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Список соединений")

        columns = ("name", "node1", "node2", "cable", "distance", "cost")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", height=12)
        for col in columns:
            tree.heading(col, text=col.capitalize())
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        def fill_connections():
            for item in tree.get_children():
                tree.delete(item)
            for conn in self.connections:
                vals = (
                    conn.name,
                    conn.node1.name,
                    conn.node2.name,
                    conn.cable.cable_name,
                    f"{conn.distance:.2f}",
                    f"{conn.connection_cost:.2f}"
                )
                tree.insert("", tk.END, values=vals)

        fill_connections()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)

        def on_edit_connection():
            item_id = tree.focus()
            if not item_id:
                messagebox.showerror("Ошибка", "Выберите соединение для редактирования.")
                return
            vals = tree.item(item_id, "values")
            conn_name = vals[0]

            conn_obj = next((c for c in self.connections if c.name == conn_name), None)
            if not conn_obj:
                messagebox.showerror("Ошибка", "Соединение не найдено.")
                return

            edit_dialog = tk.Toplevel(dialog)
            edit_dialog.title(f"Редактировать соединение {conn_name}")

            tk.Label(edit_dialog, text="Название:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
            name_e = tk.Entry(edit_dialog)
            name_e.insert(0, conn_obj.name)
            name_e.grid(row=0, column=1, padx=5, pady=5)

            tk.Label(edit_dialog, text="Узел 1:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
            node1_combo = ttk.Combobox(edit_dialog, values=[n.name for n in self.nodes], state="readonly")
            node1_combo.set(conn_obj.node1.name)
            node1_combo.grid(row=1, column=1, padx=5, pady=5)

            tk.Label(edit_dialog, text="Узел 2:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.E)
            node2_combo = ttk.Combobox(edit_dialog, values=[n.name for n in self.nodes], state="readonly")
            node2_combo.set(conn_obj.node2.name)
            node2_combo.grid(row=2, column=1, padx=5, pady=5)

            tk.Label(edit_dialog, text="Кабель:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.E)
            cable_combo = ttk.Combobox(edit_dialog, values=[c.cable_name for c in self.cables], state="readonly")
            cable_combo.set(conn_obj.cable.cable_name)
            cable_combo.grid(row=3, column=1, padx=5, pady=5)

            def on_save():
                new_name = name_e.get().strip()
                n1_name = node1_combo.get()
                n2_name = node2_combo.get()
                cab_name = cable_combo.get()

                if n1_name == n2_name:
                    messagebox.showerror("Ошибка", "Узел 1 и Узел 2 должны быть разными.")
                    return

                node1_obj = next((n for n in self.nodes if n.name == n1_name), None)
                node2_obj = next((n for n in self.nodes if n.name == n2_name), None)
                cable_obj = next((cb for cb in self.cables if cb.cable_name == cab_name), None)

                if not (node1_obj and node2_obj and cable_obj):
                    messagebox.showerror("Ошибка", "Неверные узлы или кабель.")
                    return

                conn_obj.name = new_name
                conn_obj.node1 = node1_obj
                conn_obj.node2 = node2_obj
                conn_obj.cable = cable_obj
                # Пересчёт дистанции и стоимости
                conn_obj.distance = conn_obj._calc_distance()
                conn_obj.connection_cost = conn_obj.distance * cable_obj.cost_per_unit

                fill_connections()
                self.draw_centered_grid()
                edit_dialog.destroy()

            ttk.Button(edit_dialog, text="Сохранить", command=on_save).grid(row=4, column=0, columnspan=2, pady=10)

        def on_delete_connection():
            item_id = tree.focus()
            if not item_id:
                messagebox.showerror("Ошибка", "Выберите соединение для удаления.")
                return
            vals = tree.item(item_id, "values")
            conn_name = vals[0]
            conn_obj = next((c for c in self.connections if c.name == conn_name), None)
            if not conn_obj:
                messagebox.showerror("Ошибка", "Соединение не найдено.")
                return

            self.connections.remove(conn_obj)
            fill_connections()
            self.draw_centered_grid()

        ttk.Button(btn_frame, text="Edit", command=on_edit_connection).pack(pady=5)
        ttk.Button(btn_frame, text="Delete", command=on_delete_connection).pack(pady=5)

    # --------------------------------------------------------------------------
    # Кратчайшие пути

    def show_shortest_paths_dialog(self):
        paths_dict = calculate_all_shortest_paths(self.nodes, self.connections)

        dialog = tk.Toplevel(self)
        dialog.title("Кратчайшие пути")

        row_idx = 0
        for src, dst_map in paths_dict.items():
            for dst, path_list in dst_map.items():
                if path_list:
                    path_str = " -> ".join(path_list)
                    label_text = f"{src} -> {dst}: {path_str}"
                else:
                    label_text = f"{src} -> {dst}: (нет пути)"
                tk.Label(dialog, text=label_text).grid(row=row_idx, column=0, sticky=tk.W, padx=5, pady=2)
                row_idx += 1

    # --------------------------------------------------------------------------
    # Показать потоки на каналах (с учетом новой формулы задержки)

    def show_data_flows_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Потоки по соединениям")

        columns = ("node1", "node2", "flow", "packet", "capacity", "delay")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", height=10)
        for col in columns:
            tree.heading(col, text=col)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        # Считаем flow + packet (глобальный)
        conn_data = compute_flows_on_connections(
            self.nodes, self.connections, self.traffic_matrix, self.global_packet_size
        )

        delays_list = []

        for conn, info in conn_data.items():
            flow = info["flow"]
            packet_size = info["packet"]  # это наш global_packet_size
            capacity = conn.cable.capacity

            if flow >= capacity:
                delay_str = "∞"
                delay_val = float('inf')
            else:
                # Новая формула задержки: packet_size / (capacity - flow)
                denom = capacity - flow
                if denom <= 0:
                    delay_str = "∞"
                    delay_val = float('inf')
                else:
                    delay_val = packet_size / denom
                    delay_str = f"{delay_val:.4f}"

            # Сохраняем значение для последующего усреднения (если не infinity)
            if delay_val != float('inf'):
                delays_list.append(delay_val)

            vals = (
                conn.node1.name,
                conn.node2.name,
                f"{flow}",
                f"{packet_size}",
                f"{capacity}",
                delay_str
            )
            tree.insert("", tk.END, values=vals)

        # Добавляем метку «Средняя задержка» — снизу
        avg_frame = ttk.Frame(dialog)
        avg_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        if delays_list:
            avg_delay = sum(delays_list) / len(delays_list)
            tk.Label(avg_frame, text=f"Средняя задержка (по конечным значениям): {avg_delay:.4f}")\
              .pack(side=tk.LEFT, padx=5)
        else:
            tk.Label(avg_frame, text="Нет конечных значений задержки (все ∞?)")\
              .pack(side=tk.LEFT, padx=5)

    # --------------------------------------------------------------------------
    # Поиск минимального роутера/кабеля и подсчёт сумм

    def compute_min_resources(self):
        try:
            min_routers = find_min_router_per_node(self.nodes, self.routers, self.traffic_matrix)
            min_cable = find_min_cable(self.cables, self.traffic_matrix)

            total_router_cost = sum(
                router.cost for router in min_routers.values() if router is not None
            )
            total_cable_cost = sum_cable_costs(self.connections)

            msg = "Минимальные роутеры по узлам:\n"
            for node_name, router in min_routers.items():
                if router:
                    msg += f" - {node_name}: {router.model_name} (capacity={router.capacity}, cost={router.cost})\n"
                else:
                    msg += f" - {node_name}: Нет подходящего роутера.\n"
            msg += "\n"

            if min_cable:
                msg += f"Минимальный кабель: {min_cable.cable_name}, capacity={min_cable.capacity}, cost_per_unit={min_cable.cost_per_unit}\n"
            else:
                msg += "Нет подходящего кабеля.\n"
            msg += "\n"

            msg += f"Сумма всех цен роутеров (min вариант): {total_router_cost:.2f}\n"
            msg += f"Сумма всех цен кабелей (текущая сеть): {total_cable_cost:.2f}\n"

            messagebox.showinfo("Результат", msg)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при вычислении минимальных ресурсов:\n{e}")

    # --------------------------------------------------------------------------
    # Сохранение и загрузка

    def save_data(self):
        filename = filedialog.asksaveasfilename(defaultextension=".json")
        if filename:
            try:
                save_data_to_file(
                    filename,
                    self.routers,
                    self.nodes,
                    self.connections,
                    self.traffic_matrix,
                    self.cables
                )
                messagebox.showinfo("Сохранение", "Все данные успешно сохранены.")
            except Exception as e:
                messagebox.showerror("Ошибка при сохранении", str(e))

    def load_data(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if not filename:
            return
        try:
            data = load_data_from_file(filename)
            self.routers = data["routers"]
            self.nodes = data["nodes"]
            self.connections = data["connections"]
            self.traffic_matrix = data["traffic_matrix"]
            self.cables = data.get("cables", [])

            self.draw_centered_grid()
            messagebox.showinfo("Загрузка", "Все данные успешно загружены.")
        except Exception as e:
            messagebox.showerror("Ошибка при загрузке", str(e))

# --------------------------------------------------------------------------
def apply_dark_theme(root):
    """Применяет тёмную тему к приложению."""
    root.configure(bg="#121212")  # Очень тёмный фон
    style = ttk.Style()
    style.theme_use("clam")

    # Настройка кнопок
    style.configure(
        "TButton",
        background="#1E1E1E",
        foreground="#E0E0E0",
        font=("Arial", 11),
        borderwidth=1,
        focuscolor="none",
    )
    style.map(
        "TButton",
        background=[("active", "#333333")],
        foreground=[("active", "#FFFFFF")],
    )

    # Настройка рамок (Frame) и меток (Label)
    style.configure("TFrame", background="#121212")
    style.configure("TLabel", background="#121212", foreground="#E0E0E0", font=("Arial", 11))

    # Настройка таблиц (Treeview)
    style.configure(
        "Treeview",
        background="#1E1E1E",
        foreground="#E0E0E0",
        fieldbackground="#1E1E1E",
        font=("Arial", 10),
    )
    style.map(
        "Treeview",
        background=[("selected", "#333333")],
        foreground=[("selected", "#FFFFFF")],
    )

    # Полосы прокрутки
    style.configure(
        "Vertical.TScrollbar",
        background="#1E1E1E",
        troughcolor="#121212",
        arrowcolor="#E0E0E0",
    )
    style.configure(
        "Horizontal.TScrollbar",
        background="#1E1E1E",
        troughcolor="#121212",
        arrowcolor="#E0E0E0",
    )

if __name__ == "__main__":
    app = Application()
    apply_dark_theme(app)  # Тёмная тема (необязательно)
    app.mainloop()
