import {
  requirePositioned,
  validate, index, neighbors, bfs, dfs, shortestPath, subgraph, hasTag,
  parentOf, childrenOf, ancestors, descendants, roots, isAcyclic,
  type Graph, type Node, type Edge,
} from '../src/graph';

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

/** Simple undirected graph:
 *    a -- b -- c
 *         |
 *         d
 */
const undirected: Graph = {
  nodes: [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }],
  edges: [
    { from: 'a', to: 'b' },
    { from: 'b', to: 'c' },
    { from: 'b', to: 'd' },
  ],
};

/** Directed tree (humanoid skeleton shape):
 *    root → spine → neck → head
 *                 → armL
 *                 → armR
 */
const tree: Graph = {
  directed: true,
  nodes: [
    { id: 'root' }, { id: 'spine' }, { id: 'neck' },
    { id: 'head' }, { id: 'armL' }, { id: 'armR' },
  ],
  edges: [
    { from: 'root',  to: 'spine' },
    { from: 'spine', to: 'neck' },
    { from: 'neck',  to: 'head' },
    { from: 'spine', to: 'armL', tags: ['limb', 'left'] },
    { from: 'spine', to: 'armR', tags: ['limb', 'right'] },
  ],
};

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

describe('validate', () => {
  test('clean graph passes', () => {
    expect(validate(undirected).ok).toBe(true);
    expect(validate(tree).ok).toBe(true);
  });

  test('duplicate ids flagged', () => {
    const g: Graph = { nodes: [{ id: 'a' }, { id: 'a' }], edges: [] };
    const r = validate(g);
    expect(r.ok).toBe(false);
    expect(r.issues.some(i => i.kind === 'duplicate-id')).toBe(true);
  });

  test('edge referencing missing node flagged', () => {
    const g: Graph = {
      nodes: [{ id: 'a' }],
      edges: [{ from: 'a', to: 'ghost' }],
    };
    const r = validate(g);
    expect(r.ok).toBe(false);
    const issue = r.issues.find(i => i.kind === 'edge-references-missing-node');
    expect(issue).toBeDefined();
    expect((issue as any).missing).toBe('ghost');
  });

  test('self-loop flagged by default, allowed with tag', () => {
    const g: Graph = {
      nodes: [{ id: 'a' }],
      edges: [{ from: 'a', to: 'a' }],
    };
    expect(validate(g).ok).toBe(false);
    expect(validate({
      nodes: [{ id: 'a' }],
      edges: [{ from: 'a', to: 'a', tags: ['loop'] }],
    }).ok).toBe(true);
    expect(validate(g, { allowSelfLoops: true }).ok).toBe(true);
  });

  test('orphan nodes flagged only when opted in', () => {
    const g: Graph = { nodes: [{ id: 'a' }, { id: 'b' }], edges: [] };
    expect(validate(g).ok).toBe(true);
    const r = validate(g, { flagOrphans: true });
    expect(r.ok).toBe(false);
    expect(r.issues.filter(i => i.kind === 'orphan-node').length).toBe(2);
  });

  test('duplicate undirected edges flagged regardless of direction', () => {
    const g: Graph = {
      nodes: [{ id: 'a' }, { id: 'b' }],
      edges: [
        { from: 'a', to: 'b' },
        { from: 'b', to: 'a' },
      ],
    };
    const r = validate(g);
    expect(r.issues.some(i => i.kind === 'duplicate-edge')).toBe(true);
  });

  test('directed edges a→b and b→a are not duplicates', () => {
    const g: Graph = {
      directed: true,
      nodes: [{ id: 'a' }, { id: 'b' }],
      edges: [{ from: 'a', to: 'b' }, { from: 'b', to: 'a' }],
    };
    expect(validate(g).ok).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Indexing
// ---------------------------------------------------------------------------

describe('index', () => {
  test('nodeById lookup', () => {
    const ig = index(tree);
    expect(ig.nodeById.get('head')?.id).toBe('head');
    expect(ig.nodeById.has('ghost')).toBe(false);
  });

  test('undirected adjacency is symmetric', () => {
    const ig = index(undirected);
    expect(ig.outAdj.get('a')).toEqual(['b']);
    expect(ig.outAdj.get('b')?.sort()).toEqual(['a', 'c', 'd']);
    expect(ig.inAdj.get('b')?.sort()).toEqual(['a', 'c', 'd']);
  });

  test('directed adjacency distinguishes in/out', () => {
    const ig = index(tree);
    expect(ig.outAdj.get('spine')?.sort()).toEqual(['armL', 'armR', 'neck']);
    expect(ig.inAdj.get('spine')).toEqual(['root']);
    expect(ig.inAdj.get('root')).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Traversal
// ---------------------------------------------------------------------------

describe('traversal', () => {
  test('bfs visits by layer', () => {
    const ig = index(tree);
    const order = bfs(ig, 'root');
    expect(order[0]).toBe('root');
    expect(order[1]).toBe('spine');
    // layer 2: neck, armL, armR (order depends on edge order)
    expect(order.slice(2, 5).sort()).toEqual(['armL', 'armR', 'neck']);
    expect(order[5]).toBe('head');
  });

  test('dfs visits by depth', () => {
    const ig = index(tree);
    const order = dfs(ig, 'root');
    // root → spine → (first child: neck) → head → armL → armR
    expect(order[0]).toBe('root');
    expect(order[1]).toBe('spine');
    expect(order[2]).toBe('neck');
    expect(order[3]).toBe('head');
    expect(order.slice(4).sort()).toEqual(['armL', 'armR']);
  });

  test('bfs/dfs on unknown start returns empty', () => {
    const ig = index(tree);
    expect(bfs(ig, 'ghost')).toEqual([]);
    expect(dfs(ig, 'ghost')).toEqual([]);
  });

  test('neighbors returns adjacency list', () => {
    const ig = index(undirected);
    expect([...neighbors(ig, 'b')].sort()).toEqual(['a', 'c', 'd']);
    expect(neighbors(ig, 'a')).toEqual(['b']);
  });
});

// ---------------------------------------------------------------------------
// Shortest path
// ---------------------------------------------------------------------------

describe('shortestPath', () => {
  test('path in undirected graph', () => {
    const ig = index(undirected);
    expect(shortestPath(ig, 'a', 'd')).toEqual(['a', 'b', 'd']);
    expect(shortestPath(ig, 'a', 'c')).toEqual(['a', 'b', 'c']);
  });

  test('from == to returns single-node path', () => {
    const ig = index(undirected);
    expect(shortestPath(ig, 'a', 'a')).toEqual(['a']);
  });

  test('disconnected graph returns null', () => {
    const g: Graph = {
      nodes: [{ id: 'a' }, { id: 'b' }, { id: 'x' }],
      edges: [{ from: 'a', to: 'b' }],
    };
    expect(shortestPath(index(g), 'a', 'x')).toBeNull();
  });

  test('directed path respects direction', () => {
    const g: Graph = {
      directed: true,
      nodes: [{ id: 'a' }, { id: 'b' }],
      edges: [{ from: 'a', to: 'b' }],
    };
    const ig = index(g);
    expect(shortestPath(ig, 'a', 'b')).toEqual(['a', 'b']);
    expect(shortestPath(ig, 'b', 'a')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Subgraph
// ---------------------------------------------------------------------------

describe('subgraph', () => {
  test('keep only limb edges, drop their endpoints if no other connections', () => {
    const sub = subgraph(tree, () => true, e => hasTag(e, 'limb'));
    expect(sub.edges.length).toBe(2);
    expect(sub.edges.every(e => hasTag(e, 'limb'))).toBe(true);
  });

  test('node filter drops dangling edges', () => {
    const sub = subgraph(tree, n => n.id !== 'head');
    expect(sub.nodes.find(n => n.id === 'head')).toBeUndefined();
    expect(sub.edges.find(e => e.to === 'head')).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Tree ops
// ---------------------------------------------------------------------------

describe('tree ops', () => {
  test('parentOf / childrenOf', () => {
    const ig = index(tree);
    expect(parentOf(ig, 'head')).toBe('neck');
    expect(parentOf(ig, 'root')).toBeNull();
    expect([...childrenOf(ig, 'spine')].sort()).toEqual(['armL', 'armR', 'neck']);
    expect(childrenOf(ig, 'head')).toEqual([]);
  });

  test('ancestors chain', () => {
    const ig = index(tree);
    expect(ancestors(ig, 'head')).toEqual(['neck', 'spine', 'root']);
    expect(ancestors(ig, 'root')).toEqual([]);
  });

  test('descendants', () => {
    const ig = index(tree);
    const d = descendants(ig, 'spine').sort();
    expect(d).toEqual(['armL', 'armR', 'head', 'neck']);
    expect(descendants(ig, 'head')).toEqual([]);
  });

  test('roots = nodes with no incoming edges', () => {
    const ig = index(tree);
    expect(roots(ig)).toEqual(['root']);
    // Two-tree forest.
    const forest: Graph = {
      directed: true,
      nodes: [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }],
      edges: [{ from: 'a', to: 'b' }, { from: 'c', to: 'd' }],
    };
    expect(roots(index(forest)).sort()).toEqual(['a', 'c']);
  });

  test('isAcyclic: true for tree, false for cycle', () => {
    expect(isAcyclic(index(tree))).toBe(true);
    const cyc: Graph = {
      directed: true,
      nodes: [{ id: 'a' }, { id: 'b' }, { id: 'c' }],
      edges: [
        { from: 'a', to: 'b' },
        { from: 'b', to: 'c' },
        { from: 'c', to: 'a' },
      ],
    };
    expect(isAcyclic(index(cyc))).toBe(false);
  });

  test('tree ops throw on undirected graph', () => {
    const ig = index(undirected);
    expect(() => parentOf(ig, 'a')).toThrow();
    expect(() => childrenOf(ig, 'a')).toThrow();
    expect(() => descendants(ig, 'a')).toThrow();
  });
});

// ---------------------------------------------------------------------------
// Generic payload type
// ---------------------------------------------------------------------------

describe('payload generics', () => {
  test('Graph<Point3> compiles and round-trips pos', () => {
    interface Pt { x: number; y: number; z: number; }
    const g: Graph<Pt> = {
      nodes: [
        { id: 'a', pos: { x: 0, y: 0, z: 0 } },
        { id: 'b', pos: { x: 1, y: 2, z: 3 } },
      ],
      edges: [{ from: 'a', to: 'b' }],
    };
    const ig = index(g);
    expect(ig.nodeById.get('b')?.pos).toEqual({ x: 1, y: 2, z: 3 });
  });
});

describe('requirePositioned', () => {
  it('narrows a Graph<P> with all positions into PositionedGraph<P>', () => {
    const g = {
      directed: true,
      nodes: [
        { id: 'a', pos: { x: 1, y: 2, z: 3 } },
        { id: 'b', pos: { x: 4, y: 5, z: 6 }, tags: ['leaf'] as const },
      ],
      edges: [{ from: 'a', to: 'b' }],
    };
    const pg = requirePositioned(g);
    expect(pg.nodes).toHaveLength(2);
    expect(pg.nodes[0].pos).toEqual({ x: 1, y: 2, z: 3 });
    expect(pg.nodes[1].tags).toEqual(['leaf']);
    expect(pg.edges).toEqual(g.edges);
    expect(pg.directed).toBe(true);
  });

  it('throws on the first node missing pos', () => {
    const g = {
      nodes: [
        { id: 'a', pos: { x: 1, y: 2, z: 3 } },
        { id: 'b' },
      ],
      edges: [],
    };
    expect(() => requirePositioned(g)).toThrow(/"b"/);
  });

  it('omits tags when not present', () => {
    const g = {
      nodes: [{ id: 'a', pos: { x: 0, y: 0, z: 0 } }],
      edges: [],
    };
    const pg = requirePositioned(g);
    expect('tags' in pg.nodes[0]).toBe(false);
  });

  it('omits directed when not present on input', () => {
    const g = {
      nodes: [{ id: 'a', pos: { x: 0, y: 0, z: 0 } }],
      edges: [],
    };
    const pg = requirePositioned(g);
    expect('directed' in pg).toBe(false);
  });
});
