# gui.py
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

        # --- Настройки Canvas ---
        self.canvas_width = 800
        self.canvas_height = 600
        self.center_x = self.canvas_width // 2
        self.center_y = self.canvas_height // 2
        self.SCALE = 4.0  # масштаб логических координат по умолчанию

        # --- Основные данные ---
        self.routers = []
        self.nodes = []
        self.connections = []
        self.traffic_matrix = TrafficMatrix()
        self.cables = []

        # Пример начальных данных
        default_router = Router("testNode", 9999999, 100)
        self.routers.append(default_router)
        self.cables.append(Cable("DefaultCable", 1.0, 1000))
        self.cables.append(Cable("HighSpeedCable", 2.0, 10000))

        # --- Интерфейс ---
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Верхняя панель кнопок
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

        # Рисуем изначальную сетку
        self.draw_centered_grid()

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
    # Добавление узла (оставляем без изменений)

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

        # Заполняем таблицу роутеров
        for r in self.routers:
            router_tree.insert("", tk.END, values=(r.model_name, r.capacity, r.cost))

        self.selected_router = None

        def on_router_select(event):
            item_id = router_tree.focus()
            if item_id:
                vals = router_tree.item(item_id, "values")
                model_name = vals[0]
                # Ищем наш Router в self.routers
                for router in self.routers:
                    if router.model_name == model_name:
                        self.selected_router = router
                        break

        router_tree.bind("<<TreeviewSelect>>", on_router_select)

        def on_add_router():
            """Вспомогательный диалог, чтобы добавить новый роутер."""
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
                    # Обновим таблицу роутеров
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
    # Добавление соединения (оставляем без изменений)

    def add_connection_dialog(self):
        """Окно для добавления нового соединения между узлами."""
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
            """Обновляет список узлов (OptionMenu), если появились новые."""
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
            """Вспомогательный диалог для добавления кабеля."""
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
    # Матрица нагрузки (оставляем без изменений)

    def show_traffic_matrix_dialog(self):
        """
        Окно «Матрица нагрузки»:
         - Отображает self.traffic_matrix.demands
         - Позволяет добавлять/обновлять записи (src, dst, traffic, packet_size)
         - Кнопка «Обновить» перечитывает таблицу из памяти
        """
        dialog = tk.Toplevel(self)
        dialog.title("Матрица нагрузки")

        frame_top = ttk.Frame(dialog)
        frame_top.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("src", "dst", "traffic", "packet")
        tree = ttk.Treeview(frame_top, columns=columns, show="headings", height=8)
        for col in columns:
            tree.heading(col, text=col.capitalize())
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(frame_top, orient="vertical", command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        # Заполнение таблицы
        self._fill_traffic_table(tree)

        # Блок добавления новой записи
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

        tk.Label(frame_bottom, text="packet_size:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.E)
        p_entry = tk.Entry(frame_bottom)
        p_entry.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)

        def on_add_record():
            """Добавляем (или обновляем) запись (src, dst) -> (traffic, packet_size)."""
            try:
                t_val = float(t_entry.get())
                p_val = float(p_entry.get())
                src_node = src_var.get()
                dst_node = dst_var.get()
                self.traffic_matrix.set_demand(src_node, dst_node, t_val, p_val)

                # Перезаполним таблицу
                for item in tree.get_children():
                    tree.delete(item)
                self._fill_traffic_table(tree)
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректные значения traffic/packet.")

        ttk.Button(frame_bottom, text="Добавить запись", command=on_add_record)\
            .grid(row=4, column=0, columnspan=2, pady=5)

        # Кнопка «Обновить»
        def on_refresh():
            for item in tree.get_children():
                tree.delete(item)
            self._fill_traffic_table(tree)

        ttk.Button(frame_bottom, text="Обновить", command=on_refresh)\
            .grid(row=4, column=2, padx=20, pady=5)

    def _fill_traffic_table(self, treeview: ttk.Treeview):
        """Показываем все корректные записи из self.traffic_matrix.demands."""
        for key, val in self.traffic_matrix.demands.items():
            # Ожидаем (src, dst) -> (traffic, packet_size)
            if (isinstance(key, tuple) and len(key) == 2 and
                isinstance(val, tuple) and len(val) == 2):
                src, dst = key
                traffic, packet = val
                treeview.insert("", tk.END, values=(src, dst, traffic, packet))

    # --------------------------------------------------------------------------
    # Показать узлы (таблица)

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

        # Заполнение
        for node in self.nodes:
            vals = (
                node.name,
                f"{node.x}",
                f"{node.y}",
                node.router.model_name,
                f"{node.router.capacity}",
                f"{node.router.cost}",
            )
            tree.insert("", tk.END, values=vals)

    # --------------------------------------------------------------------------
    # Показать соединения (просто список без учёта потока)

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

    # --------------------------------------------------------------------------
    # Кратчайшие пути (оставляем без изменений)

    def show_shortest_paths_dialog(self):
        from logic import calculate_all_shortest_paths
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
    # Показать потоки на каналах

    def show_data_flows_dialog(self):
        """
        Показываем суммарный поток (flow) на каждом канале (соединении),
        используя compute_flows_on_connections.
        """
        from logic import compute_flows_on_connections
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

        conn_data = compute_flows_on_connections(self.nodes, self.connections, self.traffic_matrix)
        for conn, info in conn_data.items():
            flow = info["flow"]
            packet_size = info["packet"]
            capacity = conn.cable.capacity

            if flow >= capacity:
                delay_str = "∞"
            else:
                gap = capacity - flow
                if gap <= 0:
                    delay_str = "∞"
                else:
                    delay = packet_size * (1.0 / gap)
                    delay_str = f"{delay:.4f}"

            vals = (
                conn.node1.name,
                conn.node2.name,
                f"{flow}",
                f"{packet_size}",
                f"{capacity}",
                delay_str
            )
            tree.insert("", tk.END, values=vals)

        # Добавим отладочную информацию
        print("Потоки по соединениям:")
        for conn, info in conn_data.items():
            print(f"{conn.node1.name} - {conn.node2.name}: Flow={info['flow']}, Packet={info['packet']}, Capacity={conn.cable.capacity}, Delay={delay_str}")

    # --------------------------------------------------------------------------
    # Поиск минимального роутера/кабеля и подсчёт сумм

    def compute_min_resources(self):
        from logic import find_min_router_per_node, find_min_cable, sum_router_costs, sum_cable_costs

        try:
            # Находим минимальные роутеры для каждого узла
            min_routers = find_min_router_per_node(self.nodes, self.routers, self.traffic_matrix)

            # Находим минимальный кабель для общей нагрузки
            min_cable = find_min_cable(self.cables, self.traffic_matrix)

            # Подсчитываем сумму всех цен роутеров
            total_router_cost = sum(
                router.cost for router in min_routers.values() if router is not None
            )

            # Подсчитываем сумму всех цен кабелей
            total_cable_cost = sum_cable_costs(self.connections)

            # Собираем информацию для отображения
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

            msg += f"Сумма всех цен роутеров: {total_router_cost:.2f}\n"
            msg += f"Сумма всех цен кабелей: {total_cable_cost:.2f}\n"

            # Показываем сообщение
            messagebox.showinfo("Результат", msg)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при вычислении минимальных ресурсов:\n{e}")

    # --------------------------------------------------------------------------
    # Сохранение и загрузка (оставляем без изменений)

    def save_data(self):
        """
        Сохраняем узлы, соединения, роутеры, кабели и полный traffic_matrix
        (ничего не удаляя) в один JSON-файл.
        """
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
                messagebox.showinfo("Сохранение", "Все данные (включая матрицу нагрузки) успешно сохранены.")
            except Exception as e:
                messagebox.showerror("Ошибка при сохранении", str(e))

    def load_data(self):
        """
        Загружаем все данные (включая матрицу нагрузок).
        После загрузки ничего не вырезается из матрицы.
        """
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

            # Перерисовываем Canvas
            self.draw_centered_grid()

            messagebox.showinfo("Загрузка", "Все данные (включая матрицу нагрузки) успешно загружены.")
        except Exception as e:
            messagebox.showerror("Ошибка при загрузке", str(e))

# --------------------------------------------------------------------------
# Показать потоки на каналах (добавляем отладочную информацию)

# Остальные методы остаются без изменений

def apply_dark_theme(root):
    """Применяет тёмную тему к приложению."""
    root.configure(bg="#121212")  # Очень тёмный фон
    style = ttk.Style()
    style.theme_use("clam")

    # Настройка кнопок
    style.configure(
        "TButton",
        background="#1E1E1E",  # Тёмно-серый фон
        foreground="#E0E0E0",  # Светло-серый текст
        font=("Arial", 11),
        borderwidth=1,
        focuscolor="none",
    )
    style.map(
        "TButton",
        background=[("active", "#333333")],  # Более светлый серый при наведении
        foreground=[("active", "#FFFFFF")],  # Белый текст при наведении
    )

    # Настройка рамок (Frame)
    style.configure(
        "TFrame",
        background="#121212",  # Фон совпадает с главным окном
    )

    # Настройка меток (Label)
    style.configure(
        "TLabel",
        background="#121212",
        foreground="#E0E0E0",  # Светлый текст
        font=("Arial", 11),
    )

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

    # Настройка полос прокрутки (Scrollbar)
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
    apply_dark_theme(app)  # Применяем тёмную тему
    app.mainloop()
