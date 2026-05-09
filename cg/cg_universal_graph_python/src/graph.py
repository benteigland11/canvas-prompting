from dataclasses import dataclass, field
from typing import TypeVar, Generic, Dict, List, Set, Optional

T = TypeVar('T')

@dataclass
class Node(Generic[T]):
    id: str
    payload: T
    tags: Set[str] = field(default_factory=set)

@dataclass
class Edge:
    source: str
    target: str
    tag: Optional[str] = None

class Graph(Generic[T]):
    def __init__(self):
        self.nodes: Dict[str, Node[T]] = {}
        self.edges: List[Edge] = []
        self._adj_list: Dict[str, List[str]] = {}
        self._rev_adj_list: Dict[str, List[str]] = {}

    def add_node(self, node: Node[T]):
        self.nodes[node.id] = node
        if node.id not in self._adj_list:
            self._adj_list[node.id] = []
            self._rev_adj_list[node.id] = []

    def add_edge(self, edge: Edge):
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError(f"Source or target node not found: {edge.source} -> {edge.target}")
        self.edges.append(edge)
        self._adj_list[edge.source].append(edge.target)
        self._rev_adj_list[edge.target].append(edge.source)

    def ancestors(self, node_id: str) -> Set[str]:
        """Returns all node IDs that have a path to node_id."""
        if node_id not in self.nodes:
            return set()
        
        visited = set()
        stack = [node_id]
        
        while stack:
            current = stack.pop()
            for prev in self._rev_adj_list.get(current, []):
                if prev not in visited:
                    visited.add(prev)
                    stack.append(prev)
                    
        return visited

    def descendants(self, node_id: str) -> Set[str]:
        """Returns all node IDs that node_id has a path to."""
        if node_id not in self.nodes:
            return set()
        
        visited = set()
        stack = [node_id]
        
        while stack:
            current = stack.pop()
            for nxt in self._adj_list.get(current, []):
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append(nxt)
                    
        return visited

    def topological_sort(self) -> List[str]:
        """Returns a list of node IDs in topological order. Raises ValueError if a cycle is detected."""
        in_degree = {node_id: 0 for node_id in self.nodes}
        for edge in self.edges:
            in_degree[edge.target] += 1
            
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            for nxt in self._adj_list.get(current, []):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
                    
        if len(result) != len(self.nodes):
            raise ValueError("Graph contains a cycle and cannot be topologically sorted.")
            
        return result
