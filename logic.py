# logic.py

import heapq
import json
from typing import List, Dict, Tuple
from math import sqrt
from models import Node, Connection, TrafficMatrix, Router, Cable

def dijkstra_with_paths(graph: Dict[str, Dict[str, float]], start: str):
    """Алгоритм Дейкстры, возвращающий (distances, predecessors)."""
    distances = {n: float('inf') for n in graph}
    distances[start] = 0
    visited = set()
    predecessors = {n: None for n in graph}

    queue = [(0, start)]
    while queue:
        cur_dist, node = heapq.heappop(queue)
        if node in visited:
            continue
        visited.add(node)

        for neighbor, weight in graph[node].items():
            dist = cur_dist + weight
            if dist < distances[neighbor]:
                distances[neighbor] = dist
                predecessors[neighbor] = node
                heapq.heappush(queue, (dist, neighbor))
    return distances, predecessors

def reconstruct_path(predecessors: Dict[str, str], start: str, end: str) -> List[str]:
    """
    Восстанавливаем путь из start в end по словарю predecessors.
    """
    path = []
    current = end
    while current is not None:
        path.append(current)
        if current == start:
            break
        current = predecessors[current]
    path.reverse()
    if path and path[0] == start:
        return path
    return []

def build_graph(nodes: List[Node], connections: List[Connection]) -> Dict[str, Dict[str, float]]:
    """
    Создаём словарь смежности вида:
    {
       node_name: {neighbor_name: edge_cost, ...},
       ...
    }
    """
    graph = {node.name: {} for node in nodes}
    for conn in connections:
        n1, n2 = conn.node1.name, conn.node2.name
        cost = conn.connection_cost
        graph[n1][n2] = cost
        graph[n2][n1] = cost
    return graph

def calculate_all_shortest_paths(nodes: List[Node], connections: List[Connection]) -> Dict[str, Dict[str, List[str]]]:
    """
    Для каждого узла считаем кратчайшие пути (списки узлов) до всех остальных.
    Возвращаем { src_name: { dst_name: [src, ..., dst], ... }, ... }
    """
    graph = build_graph(nodes, connections)
    result = {}
    for node in nodes:
        src = node.name
        dist_map, pred_map = dijkstra_with_paths(graph, src)
        result[src] = {}
        for other in graph:
            if other != src:
                path_list = reconstruct_path(pred_map, src, other)
                result[src][other] = path_list
    return result

def calculate_data_flows(paths_dict: Dict[str, Dict[str, List[str]]],
                         traffic_matrix: TrafficMatrix) -> List[Tuple[str, str, float]]:
    """
    Простой расчёт потоков. Возвращаем список (src, dst, traffic).
    Здесь главное - корректно обойти traffic_matrix.demands.
    """
    flows = []

    # Проверяем формат данных в demands
    for key, val in traffic_matrix.demands.items():
        # Ожидаем, что key = (src, dst), val = (traffic, packet_size)
        if (isinstance(key, tuple) and len(key) == 2 and
            isinstance(val, tuple) and len(val) == 2):
            src, dst = key
            traffic, packet_size = val

            # Проверяем, есть ли путь
            if src in paths_dict and dst in paths_dict[src]:
                path = paths_dict[src][dst]
                if path:  # если путь не пуст
                    flows.append((src, dst, traffic))
        else:
            # Если ключ/значение не соответствуют формату — пропустим
            pass

    return flows

def compute_flows_on_connections(nodes: List[Node],
                                 connections: List[Connection],
                                 traffic_matrix: TrafficMatrix) -> Dict[Connection, Dict[str, float]]:
    """
    Для каждого соединения считаем:
      - Суммарный трафик, проходящий через него (flow)
      - Максимальный packet_size (packet) среди всех потоков, которые идут через это соединение

    Возвращаем словарь:
      {
        conn: {
           "flow": float,
           "packet": float
        },
        ...
      }
    """

    # 1) Считаем кратчайшие пути
    paths_dict = calculate_all_shortest_paths(nodes, connections)

    # 2) Подготовим словарь с начальными значениями
    result = {}
    for conn in connections:
        result[conn] = {"flow": 0.0, "packet": 0.0}

    # 3) Подготовим быстрый поиск соединений через frozenset
    conn_map = {}
    for conn in connections:
        key = frozenset([conn.node1.name, conn.node2.name])
        conn_map[key] = conn

    # 4) Идём по каждой записи матрицы нагрузки
    for key, val in traffic_matrix.demands.items():
        if (isinstance(key, tuple) and len(key) == 2 and
            isinstance(val, tuple) and len(val) == 2):
            src, dst = key
            traffic, packet_size = val

            path = paths_dict.get(src, {}).get(dst, [])
            for i in range(len(path) - 1):
                n1, n2 = path[i], path[i+1]
                ckey = frozenset([n1, n2])
                if ckey in conn_map:
                    c = conn_map[ckey]
                    result[c]["flow"] += traffic
                    if packet_size > result[c]["packet"]:
                        result[c]["packet"] = packet_size

    return result

def find_min_router(routers: List[Router], traffic_matrix: TrafficMatrix):
    """
    По суммарному трафику ищем роутер, который имеет capacity >= total_traffic.
    Из таких - выбираем роутер с минимальной cost.
    Возвращаем None, если не нашли.
    """
    total_traffic = 0.0
    for key, val in traffic_matrix.demands.items():
        if (isinstance(key, tuple) and len(key) == 2 and
            isinstance(val, tuple) and len(val) == 2):
            traffic, _ = val
            total_traffic += traffic

    feasible_routers = [r for r in routers if r.capacity >= total_traffic]
    if feasible_routers:
        return min(feasible_routers, key=lambda r: r.cost)
    return None

def find_min_router_per_node(nodes: List[Node], routers: List[Router], traffic_matrix: TrafficMatrix) -> Dict[str, Router]:
    """
    Для каждого узла находит минимальный по стоимости роутер, который может обработать исходящий трафик этого узла.

    :param nodes: Список узлов.
    :param routers: Список доступных роутеров.
    :param traffic_matrix: Объект TrafficMatrix с нагрузками.
    :return: Словарь {node_name: Router}.
    """
    node_traffic = {node.name: 0.0 for node in nodes}

    # Считаем суммарный исходящий трафик для каждого узла
    for (src, dst), (traffic, _) in traffic_matrix.demands.items():
        if src in node_traffic:
            node_traffic[src] += traffic

    # Для каждого узла выбираем минимальный по стоимости роутер, способный обработать его нагрузку
    min_routers = {}
    for node in nodes:
        traffic = node_traffic.get(node.name, 0.0)
        feasible_routers = [r for r in routers if r.capacity >= traffic]
        if feasible_routers:
            # Выбираем роутер с минимальной стоимостью
            min_router = min(feasible_routers, key=lambda r: r.cost)
            min_routers[node.name] = min_router
        else:
            min_routers[node.name] = None  # Нет подходящего роутера

    return min_routers

def find_min_cable(cables: List[Cable], traffic_matrix: TrafficMatrix):
    """
    Аналогично для кабеля: ищем кабель, у которого capacity >= total_traffic.
    Из подходящих - выбираем тот, у которого cost_per_unit минимален.
    """
    total_traffic = 0.0
    for key, val in traffic_matrix.demands.items():
        if (isinstance(key, tuple) and len(key) == 2 and
            isinstance(val, tuple) and len(val) == 2):
            traffic, _ = val
            total_traffic += traffic

    feasible_cables = [c for c in cables if c.capacity >= total_traffic]
    if feasible_cables:
        return min(feasible_cables, key=lambda c: c.cost_per_unit)
    return None

def sum_router_costs(nodes: List[Node]) -> float:
    """
    Считает сумму цен роутеров, установленных на узлах.

    :param nodes: Список узлов.
    :return: Сумма цен роутеров.
    """
    return sum(node.router.cost for node in nodes if node.router is not None)

def sum_cable_costs(connections: List[Connection]) -> float:
    """
    Считает сумму цен всех кабелей в соединениях.

    :param connections: Список соединений.
    :return: Сумма цен кабелей.
    """
    return sum(conn.connection_cost for conn in connections)

def save_data_to_file(filename, routers: List[Router], nodes: List[Node],
                     connections: List[Connection], traffic_matrix: TrafficMatrix,
                     cables: List[Cable]):
    """
    Сохраняет все данные (включая полную матрицу нагрузок) в JSON.
    """
    data = {
        "routers": [
            {
                "model_name": r.model_name,
                "capacity": r.capacity,
                "cost": r.cost
            }
            for r in routers
        ],
        "nodes": [
            {
                "name": n.name,
                "x": n.x,
                "y": n.y,
                "router_model_name": n.router.model_name if n.router else None
            }
            for n in nodes
        ],
        "connections": [
            {
                "name": c.name,
                "node1": c.node1.name,
                "node2": c.node2.name,
                "cable_name": c.cable.cable_name,
                "distance": c.distance,
                "connection_cost": c.connection_cost
            }
            for c in connections
        ],
        "cables": [
            {
                "cable_name": cab.cable_name,
                "cost_per_unit": cab.cost_per_unit,
                "capacity": cab.capacity
            }
            for cab in cables
        ],
        # Сериализуем traffic_matrix.demands как список словарей
        "traffic_matrix": [
            {
                "src": src,
                "dst": dst,
                "traffic": traffic,
                "packet_size": packet_size
            }
            for (src, dst), (traffic, packet_size) in traffic_matrix.demands.items()
        ]
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_data_from_file(filename):
    """
    Загружает все данные (включая полную матрицу нагрузок) из JSON.
    """
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    # --- Восстанавливаем роутеры ---
    routers = []
    for r_dict in data.get("routers", []):
        model_name = r_dict["model_name"]
        capacity = r_dict["capacity"]
        cost = r_dict["cost"]
        routers.append(Router(model_name, capacity, cost))

    # --- Восстанавливаем кабели ---
    cables = []
    for c_dict in data.get("cables", []):
        name = c_dict["cable_name"]
        c_cost = c_dict["cost_per_unit"]
        cap = c_dict["capacity"]
        cables.append(Cable(name, c_cost, cap))

    # --- Восстанавливаем узлы ---
    nodes = []
    for n_dict in data.get("nodes", []):
        x = n_dict["x"]
        y = n_dict["y"]
        name = n_dict["name"]

        router_name = n_dict["router_model_name"]
        # Находим сам Router (по имени) в списке routers
        found_router = next((r for r in routers if r.model_name == router_name), None)
        if router_name and not found_router:
            raise ValueError(f"Router with model name '{router_name}' not found for node '{name}'.")

        # Создаём Node
        node_obj = Node(x, y, name, found_router)
        nodes.append(node_obj)

    # --- Восстанавливаем соединения ---
    connections = []
    for c_dict in data.get("connections", []):
        conn_name = c_dict["name"]
        node1_name = c_dict["node1"]
        node2_name = c_dict["node2"]
        cable_name = c_dict["cable_name"]
        distance = c_dict["distance"]
        connection_cost = c_dict["connection_cost"]

        # Находим объекты node1, node2 и cable
        node1_obj = next((n for n in nodes if n.name == node1_name), None)
        node2_obj = next((n for n in nodes if n.name == node2_name), None)
        cable_obj = next((c for c in cables if c.cable_name == cable_name), None)

        if not node1_obj or not node2_obj or not cable_obj:
            raise ValueError(f"Connection '{conn_name}' refers to non-existent nodes or cable.")

        conn = Connection(conn_name, node1_obj, node2_obj, cable_obj)
        # Устанавливаем distance и connection_cost, чтобы избежать пересчёта
        conn.distance = distance
        conn.connection_cost = connection_cost
        connections.append(conn)

    # --- Восстанавливаем traffic_matrix ---
    traffic_matrix = TrafficMatrix()
    for row in data.get("traffic_matrix", []):
        src = row["src"]
        dst = row["dst"]
        traffic = row["traffic"]
        packet_size = row["packet_size"]
        traffic_matrix.set_demand(src, dst, traffic, packet_size)

    return {
        "routers": routers,
        "nodes": nodes,
        "connections": connections,
        "traffic_matrix": traffic_matrix,
        "cables": cables
    }
