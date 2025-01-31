from math import sqrt

class Router:
    """Класс для описания роутера."""
    def __init__(self, model_name: str, capacity: int, cost: float):
        self.model_name = model_name
        self.capacity = capacity
        self.cost = cost

    def __repr__(self):
        return f"Router({self.model_name}, capacity={self.capacity}, cost={self.cost})"


class Node:
    """Класс для описания узла в сети."""
    def __init__(self, x: float, y: float, name: str, router: 'Router'):
        """
        :param x: Логическая координата X
        :param y: Логическая координата Y
        :param name: Название узла
        :param router: Объект Router
        """
        self.x = x
        self.y = y
        self.name = name
        self.router = router

    def __repr__(self):
        return f"Node({self.name}, x={self.x}, y={self.y}, router={self.router.model_name})"


class Cable:
    """Класс для хранения данных о кабеле."""
    def __init__(self, cable_name: str, cost_per_unit: float, capacity: int):
        self.cable_name = cable_name
        self.cost_per_unit = cost_per_unit
        self.capacity = capacity

    def __repr__(self):
        return f"Cable({self.cable_name}, cost={self.cost_per_unit}, cap={self.capacity})"


class Connection:
    """Класс, описывающий соединение между двумя узлами."""
    def __init__(self, name: str, node1: Node, node2: Node, cable: Cable):
        self.name = name
        self.node1 = node1
        self.node2 = node2
        self.cable = cable
        self.distance = self._calc_distance()
        self.connection_cost = self.distance * cable.cost_per_unit

    def _calc_distance(self):
        return sqrt((self.node2.x - self.node1.x)**2 + (self.node1.y - self.node2.y)**2)

    def __repr__(self):
        return (f"Connection({self.name}, {self.node1.name}-{self.node2.name}, "
                f"dist={self.distance:.2f}, cost={self.connection_cost:.2f})")


class TrafficMatrix:
    """Класс для представления матрицы нагрузки."""
    def __init__(self):
        # Ожидаемый формат: {(src_name, dst_name): (traffic, packet_size)}
        self.demands = {}

    def set_demand(self, source: str, target: str, traffic: float, packet_size: float):
        if traffic < 0 or packet_size < 0:
            raise ValueError("Нельзя использовать отрицательные значения.")
        self.demands[(source, target)] = (traffic, packet_size)

    def get_demand(self, source: str, target: str):
        return self.demands.get((source, target), (0.0, 0.0))

    def __repr__(self):
        return f"TrafficMatrix({self.demands})"
