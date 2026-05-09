import pytest
from src.graph import Node, Edge, Graph

def test_graph_operations():
    g = Graph[str]()
    g.add_node(Node("A", "payload A"))
    g.add_node(Node("B", "payload B"))
    g.add_node(Node("C", "payload C"))
    
    g.add_edge(Edge("A", "B"))
    g.add_edge(Edge("B", "C"))
    
    assert g.ancestors("C") == {"A", "B"}
    assert g.descendants("A") == {"B", "C"}
    assert g.topological_sort() == ["A", "B", "C"]

def test_cycle():
    g = Graph[str]()
    g.add_node(Node("A", ""))
    g.add_node(Node("B", ""))
    g.add_edge(Edge("A", "B"))
    g.add_edge(Edge("B", "A"))
    
    with pytest.raises(ValueError):
        g.topological_sort()
