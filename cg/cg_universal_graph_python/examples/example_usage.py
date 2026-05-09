import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.graph import Node, Edge, Graph

def main():
    g = Graph[str]()
    
    # Add nodes
    g.add_node(Node("System", "Act as a helpful assistant"))
    g.add_node(Node("Context1", "User is on Linux"))
    g.add_node(Node("Context2", "User is using Python"))
    g.add_node(Node("Prompt", "Write a python script"))
    
    # Wire them up
    g.add_edge(Edge("System", "Prompt"))
    g.add_edge(Edge("Context1", "Prompt"))
    g.add_edge(Edge("Context2", "Prompt"))
    
    # Topology and Ancestry
    print("Ancestors of Prompt:", g.ancestors("Prompt"))
    print("Topological order:", g.topological_sort())

if __name__ == "__main__":
    main()
