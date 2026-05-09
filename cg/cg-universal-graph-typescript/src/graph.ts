/**
 * graph — Layer 1 of the 6-layer stack.
 *
 * A typed graph: nodes with ids + optional payload, edges referencing nodes
 * by id, both carrying tag sets. Pure data, deterministic, no geometry
 * opinions — node payload is generic so callers pick their own position
 * type (Vec3, Vec2, whatever).
 *
 * Validation returns a structured error list (never throws). Traversal and
 * tree queries are plain functions over the graph data.
 */

export interface Node<P = unknown> {
  id: string;
  /** Optional payload — typically a position, but arbitrary. */
  pos?: P;
  /** Free-form tags used by higher layers to filter/constrain. */
  tags?: readonly string[];
}

export interface Edge {
  from: string;
  to: string;
  tags?: readonly string[];
}

export interface Graph<P = unknown> {
  nodes: readonly Node<P>[];
  edges: readonly Edge[];
  /** If true, edges are directed (from → to). Default: false (undirected). */
  directed?: boolean;
}

/**
 * A node whose payload (typically position) is present — non-optional `pos`.
 * Use when downstream code requires a payload and should not do its own
 * narrowing.
 */
export interface PositionedNode<P> {
  id: string;
  pos: P;
  tags?: readonly string[];
}

/**
 * A graph where every node has a non-optional payload. Structurally compatible
 * with the input shapes of spatial-queries and skeleton-fk; use
 * `requirePositioned(g)` to convert a `Graph<P>` to this variant (throws on
 * missing `pos`).
 */
export interface PositionedGraph<P> {
  nodes: readonly PositionedNode<P>[];
  edges: readonly Edge[];
  directed?: boolean;
}

export type ValidationIssue =
  | { kind: 'duplicate-id'; id: string }
  | { kind: 'edge-references-missing-node'; edge: Edge; missing: string }
  | { kind: 'self-loop'; edge: Edge }
  | { kind: 'orphan-node'; id: string }
  | { kind: 'duplicate-edge'; edge: Edge };

export interface ValidationResult {
  ok: boolean;
  issues: ValidationIssue[];
}

export interface ValidationOptions {
  /** If false (default), self-loops are allowed only when the edge carries
   *  the tag 'loop' (explicit opt-in). If true, self-loops are unconditionally
   *  allowed without a tag. */
  allowSelfLoops?: boolean;
  /** If true, nodes with no incident edges are flagged as orphans. Default: false. */
  flagOrphans?: boolean;
  /** If true, duplicate edges (same from/to, respecting directedness) are flagged. Default: true. */
  flagDuplicateEdges?: boolean;
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

export function validate<P>(
  g: Graph<P>,
  opts: ValidationOptions = {},
): ValidationResult {
  const allowSelfLoops = opts.allowSelfLoops ?? false;
  const flagOrphans = opts.flagOrphans ?? false;
  const flagDuplicateEdges = opts.flagDuplicateEdges ?? true;

  const issues: ValidationIssue[] = [];

  const seen = new Set<string>();
  for (const n of g.nodes) {
    if (seen.has(n.id)) issues.push({ kind: 'duplicate-id', id: n.id });
    seen.add(n.id);
  }
  const ids = seen;

  for (const e of g.edges) {
    if (!ids.has(e.from)) {
      issues.push({ kind: 'edge-references-missing-node', edge: e, missing: e.from });
    }
    if (!ids.has(e.to)) {
      issues.push({ kind: 'edge-references-missing-node', edge: e, missing: e.to });
    }
    if (e.from === e.to) {
      const tagged = (e.tags ?? []).includes('loop');
      if (!allowSelfLoops && !tagged) {
        issues.push({ kind: 'self-loop', edge: e });
      }
    }
  }

  if (flagDuplicateEdges) {
    const key = (e: Edge) =>
      g.directed ? `${e.from}->${e.to}` : [e.from, e.to].sort().join('--');
    const edgeSeen = new Set<string>();
    for (const e of g.edges) {
      const k = key(e);
      if (edgeSeen.has(k)) issues.push({ kind: 'duplicate-edge', edge: e });
      edgeSeen.add(k);
    }
  }

  if (flagOrphans) {
    const touched = new Set<string>();
    for (const e of g.edges) { touched.add(e.from); touched.add(e.to); }
    for (const n of g.nodes) {
      if (!touched.has(n.id)) issues.push({ kind: 'orphan-node', id: n.id });
    }
  }

  return { ok: issues.length === 0, issues };
}

// ---------------------------------------------------------------------------
// Indexed view (built once, reused across queries)
// ---------------------------------------------------------------------------

export interface IndexedGraph<P = unknown> {
  graph: Graph<P>;
  nodeById: ReadonlyMap<string, Node<P>>;
  /** Outgoing neighbors. For undirected graphs, adjacency goes both ways. */
  outAdj: ReadonlyMap<string, readonly string[]>;
  /** Incoming neighbors. For undirected graphs, equals outAdj. */
  inAdj: ReadonlyMap<string, readonly string[]>;
}

export function index<P>(g: Graph<P>): IndexedGraph<P> {
  const nodeById = new Map<string, Node<P>>();
  for (const n of g.nodes) nodeById.set(n.id, n);

  const out = new Map<string, string[]>();
  const incoming = new Map<string, string[]>();
  for (const n of g.nodes) { out.set(n.id, []); incoming.set(n.id, []); }

  for (const e of g.edges) {
    if (!out.has(e.from) || !out.has(e.to)) continue;
    out.get(e.from)!.push(e.to);
    incoming.get(e.to)!.push(e.from);
    if (!g.directed) {
      out.get(e.to)!.push(e.from);
      incoming.get(e.from)!.push(e.to);
    }
  }
  return { graph: g, nodeById, outAdj: out, inAdj: incoming };
}

// ---------------------------------------------------------------------------
// Traversal
// ---------------------------------------------------------------------------

export function neighbors<P>(ig: IndexedGraph<P>, id: string): readonly string[] {
  return ig.outAdj.get(id) ?? [];
}

export function bfs<P>(ig: IndexedGraph<P>, start: string): string[] {
  if (!ig.nodeById.has(start)) return [];
  const visited = new Set<string>([start]);
  const order: string[] = [];
  const queue: string[] = [start];
  while (queue.length) {
    const cur = queue.shift()!;
    order.push(cur);
    for (const n of neighbors(ig, cur)) {
      if (!visited.has(n)) { visited.add(n); queue.push(n); }
    }
  }
  return order;
}

export function dfs<P>(ig: IndexedGraph<P>, start: string): string[] {
  if (!ig.nodeById.has(start)) return [];
  const visited = new Set<string>();
  const order: string[] = [];
  const stack: string[] = [start];
  while (stack.length) {
    const cur = stack.pop()!;
    if (visited.has(cur)) continue;
    visited.add(cur);
    order.push(cur);
    const ns = neighbors(ig, cur);
    for (let i = ns.length - 1; i >= 0; i--) {
      if (!visited.has(ns[i])) stack.push(ns[i]);
    }
  }
  return order;
}

export function shortestPath<P>(
  ig: IndexedGraph<P>, from: string, to: string,
): string[] | null {
  if (!ig.nodeById.has(from) || !ig.nodeById.has(to)) return null;
  if (from === to) return [from];
  const prev = new Map<string, string>();
  const visited = new Set<string>([from]);
  const queue: string[] = [from];
  while (queue.length) {
    const cur = queue.shift()!;
    for (const n of neighbors(ig, cur)) {
      if (visited.has(n)) continue;
      visited.add(n);
      prev.set(n, cur);
      if (n === to) {
        const path: string[] = [to];
        let c: string | undefined = to;
        while ((c = prev.get(c!)) !== undefined) path.unshift(c);
        return path;
      }
      queue.push(n);
    }
  }
  return null;
}

export function subgraph<P>(
  g: Graph<P>,
  nodeFilter: (n: Node<P>) => boolean,
  edgeFilter: (e: Edge) => boolean = () => true,
): Graph<P> {
  const nodes = g.nodes.filter(nodeFilter);
  const keepIds = new Set(nodes.map(n => n.id));
  const edges = g.edges.filter(e =>
    keepIds.has(e.from) && keepIds.has(e.to) && edgeFilter(e),
  );
  return { nodes, edges, directed: g.directed };
}

export function hasTag(tagged: { tags?: readonly string[] }, tag: string): boolean {
  return (tagged.tags ?? []).includes(tag);
}

// ---------------------------------------------------------------------------
// Tree ops (interpret graph as rooted tree via directed edges parent → child)
// ---------------------------------------------------------------------------

export function parentOf<P>(ig: IndexedGraph<P>, id: string): string | null {
  if (!ig.graph.directed) {
    throw new Error('parentOf requires a directed graph');
  }
  const parents = ig.inAdj.get(id) ?? [];
  return parents.length > 0 ? parents[0] : null;
}

export function childrenOf<P>(ig: IndexedGraph<P>, id: string): readonly string[] {
  if (!ig.graph.directed) {
    throw new Error('childrenOf requires a directed graph');
  }
  return ig.outAdj.get(id) ?? [];
}

export function ancestors<P>(ig: IndexedGraph<P>, id: string): string[] {
  const chain: string[] = [];
  let cur: string | null = parentOf(ig, id);
  const seen = new Set<string>();
  while (cur && !seen.has(cur)) {
    chain.push(cur);
    seen.add(cur);
    cur = parentOf(ig, cur);
  }
  return chain;
}

export function descendants<P>(ig: IndexedGraph<P>, id: string): string[] {
  if (!ig.graph.directed) {
    throw new Error('descendants requires a directed graph');
  }
  const out: string[] = [];
  const stack: string[] = [...childrenOf(ig, id)].reverse();
  const visited = new Set<string>([id]);
  while (stack.length) {
    const cur = stack.pop()!;
    if (visited.has(cur)) continue;
    visited.add(cur);
    out.push(cur);
    const kids = childrenOf(ig, cur);
    for (let i = kids.length - 1; i >= 0; i--) stack.push(kids[i]);
  }
  return out;
}

export function roots<P>(ig: IndexedGraph<P>): string[] {
  const out: string[] = [];
  for (const n of ig.graph.nodes) {
    if ((ig.inAdj.get(n.id) ?? []).length === 0) out.push(n.id);
  }
  return out;
}

export function isAcyclic<P>(ig: IndexedGraph<P>): boolean {
  if (!ig.graph.directed) return true;
  const inDeg = new Map<string, number>();
  for (const n of ig.graph.nodes) inDeg.set(n.id, (ig.inAdj.get(n.id) ?? []).length);
  const queue: string[] = [];
  for (const [id, d] of inDeg) if (d === 0) queue.push(id);
  let removed = 0;
  while (queue.length) {
    const cur = queue.shift()!;
    removed++;
    for (const c of ig.outAdj.get(cur) ?? []) {
      inDeg.set(c, inDeg.get(c)! - 1);
      if (inDeg.get(c) === 0) queue.push(c);
    }
  }
  return removed === ig.graph.nodes.length;
}

/**
 * Narrow a `Graph<P>` to a `PositionedGraph<P>` — asserting every node has a
 * non-nullish `pos`. Throws on the first node that does not.
 *
 * Fixes a common integration-test seam: downstream widgets (spatial-queries,
 * skeleton-fk) require positions on every node, but `Graph<P>` leaves `pos`
 * optional (e.g. for abstract graph topology). Call once at the boundary
 * instead of shimming inside each downstream call.
 */
export function requirePositioned<P>(g: Graph<P>): PositionedGraph<P> {
  const nodes: PositionedNode<P>[] = g.nodes.map(n => {
    if (n.pos === undefined || n.pos === null) {
      throw new Error(`requirePositioned: node "${n.id}" has no pos`);
    }
    return { id: n.id, pos: n.pos, ...(n.tags ? { tags: n.tags } : {}) };
  });
  return { nodes, edges: g.edges, ...(g.directed !== undefined ? { directed: g.directed } : {}) };
}
