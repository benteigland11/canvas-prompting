import { Graph, Node, Edge, index, descendants, IndexedGraph } from './graph';

export type Listener = () => void;

export class ReactiveGraphStore<P = unknown> {
  private _graph: Graph<P>;
  private _indexed: IndexedGraph<P>;
  private _staleNodes = new Set<string>();
  private _listeners = new Set<Listener>();

  constructor(initialGraph: Graph<P> = { nodes: [], edges: [], directed: true }) {
    this._graph = initialGraph;
    this._indexed = index(this._graph);
  }

  get graph(): Graph<P> {
    return this._graph;
  }
  
  get staleNodes(): ReadonlySet<string> {
    return this._staleNodes;
  }

  subscribe(listener: Listener): () => void {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  private _notify() {
    for (const listener of this._listeners) {
      listener();
    }
  }

  private _updateGraph(newGraph: Graph<P>) {
    this._graph = newGraph;
    this._indexed = index(this._graph);
  }

  setGraph(graph: Graph<P>) {
    this._updateGraph(graph);
    this._staleNodes.clear();
    this._notify();
  }

  addNode(node: Node<P>) {
    this._updateGraph({
      ...this._graph,
      nodes: [...this._graph.nodes, node]
    });
    this._notify();
  }

  updateNode(id: string, updates: Partial<Node<P>>) {
    let found = false;
    const nextNodes = this._graph.nodes.map(n => {
      if (n.id === id) {
        found = true;
        return { ...n, ...updates };
      }
      return n;
    });

    if (found) {
      this._updateGraph({ ...this._graph, nodes: nextNodes });
      this.markStale(id); // marks this and descendants and notifies
    }
  }

  addEdge(edge: Edge) {
    this._updateGraph({
      ...this._graph,
      edges: [...this._graph.edges, edge]
    });
    // Adding an edge means the target now has new context, so it is stale.
    this.markStale(edge.to);
  }

  markStale(nodeId: string) {
    if (!this._indexed.nodeById.has(nodeId)) return;
    
    // Create new Set so React's useSyncExternalStore detects state change on the set itself if needed
    // but since we only trigger notify(), the hook usually just reads isStale
    this._staleNodes.add(nodeId);
    
    // Mark all descendants as stale using the universal graph's traversal
    const kids = descendants(this._indexed, nodeId);
    for (const kidId of kids) {
      this._staleNodes.add(kidId);
    }
    
    this._notify();
  }

  clearStale(nodeId: string) {
    if (this._staleNodes.has(nodeId)) {
      this._staleNodes.delete(nodeId);
      this._notify();
    }
  }
  
  isStale(nodeId: string): boolean {
    return this._staleNodes.has(nodeId);
  }
}
