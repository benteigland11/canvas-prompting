import { test, expect } from 'vitest';
import { ReactiveGraphStore } from '../src/reactive_stale_store';
import {
  validate, index, bfs, dfs, shortestPath, subgraph, hasTag,
  parentOf, childrenOf, ancestors, descendants, roots, isAcyclic, requirePositioned
} from '../src/graph';

test('ReactiveGraphStore functionality', () => {
  const store = new ReactiveGraphStore();
  let notified = 0;
  store.subscribe(() => notified++);

  store.addNode({ id: '1' });
  expect(store.graph.nodes.length).toBe(1);

  store.updateNode('1', { tags: ['test'] });
  expect(store.graph.nodes[0].tags).toEqual(['test']);
  expect(store.isStale('1')).toBe(true);

  store.clearStale('1');
  expect(store.isStale('1')).toBe(false);

  store.addNode({ id: '2' });
  store.addEdge({ from: '1', to: '2' });
  expect(store.isStale('2')).toBe(true);
  
  store.setGraph({ nodes: [{id: '1'}], edges: [], directed: true });
  expect(store.graph.nodes.length).toBe(1);
  expect(store.staleNodes.size).toBe(0);
});

test('graph validation', () => {
  const g1 = { nodes: [{id: '1'}, {id: '1'}], edges: [] };
  expect(validate(g1).ok).toBe(false); // duplicate id

  const g2 = { nodes: [{id: '1'}], edges: [{from: '1', to: '2'}] };
  expect(validate(g2).ok).toBe(false); // missing node

  const g3 = { nodes: [{id: '1'}], edges: [{from: '1', to: '1'}] };
  expect(validate(g3).ok).toBe(false); // self loop
  expect(validate(g3, {allowSelfLoops: true}).ok).toBe(true);
  
  const g4 = { nodes: [{id: '1'}, {id: '2'}], edges: [] };
  expect(validate(g4, {flagOrphans: true}).ok).toBe(false);
  
  const g5 = { nodes: [{id:'1'}, {id:'2'}], edges: [{from:'1', to:'2'}, {from:'1', to:'2'}] };
  expect(validate(g5).ok).toBe(false);
});

test('graph indexing and traversals', () => {
  const g = {
    nodes: [{id: '1'}, {id: '2'}, {id: '3'}],
    edges: [{from: '1', to: '2'}, {from: '2', to: '3'}],
    directed: true
  };
  const ig = index(g);

  expect(bfs(ig, '1')).toEqual(['1', '2', '3']);
  expect(dfs(ig, '1')).toEqual(['1', '2', '3']);
  expect(shortestPath(ig, '1', '3')).toEqual(['1', '2', '3']);
  expect(shortestPath(ig, '1', '1')).toEqual(['1']);
  expect(shortestPath(ig, '3', '1')).toBeNull();

  const sub = subgraph(g, n => n.id !== '3');
  expect(sub.nodes.length).toBe(2);

  expect(hasTag({tags: ['a']}, 'a')).toBe(true);
  expect(hasTag({}, 'a')).toBe(false);

  expect(parentOf(ig, '2')).toBe('1');
  expect(childrenOf(ig, '1')).toEqual(['2']);
  expect(ancestors(ig, '3')).toEqual(['2', '1']);
  expect(descendants(ig, '1')).toEqual(['2', '3']);
  expect(roots(ig)).toEqual(['1']);
  expect(isAcyclic(ig)).toBe(true);

  const cyclic = { nodes: [{id:'1'}], edges: [{from:'1', to:'1'}], directed: true };
  expect(isAcyclic(index(cyclic))).toBe(false);

  // tree ops throw on undirected
  const igU = index({ ...g, directed: false });
  expect(() => parentOf(igU, '2')).toThrow();
  expect(() => childrenOf(igU, '1')).toThrow();
  expect(() => descendants(igU, '1')).toThrow();

  const posG = requirePositioned({ nodes: [{id: '1', pos: [0,0]}], edges: [] });
  expect(posG.nodes[0].pos).toEqual([0,0]);

  expect(() => requirePositioned({ nodes: [{id: '1'}], edges: [] })).toThrow();
});

test('undirected graph behavior', () => {
  const g = {
    nodes: [{id: 'A'}, {id: 'B'}],
    edges: [{from: 'A', to: 'B'}]
  };
  const ig = index(g);
  expect(bfs(ig, 'B')).toEqual(['B', 'A']); // works in reverse
  expect(dfs(ig, 'B')).toEqual(['B', 'A']);
});

test('traversal edge cases', () => {
  const g = { nodes: [{id:'A'}], edges: [] };
  const ig = index(g);
  expect(bfs(ig, 'B')).toEqual([]);
  expect(dfs(ig, 'B')).toEqual([]);
  expect(shortestPath(ig, 'A', 'B')).toBeNull();
});

test('validate duplicate edge key', () => {
  const g = { nodes: [{id:'1'}, {id:'2'}], edges: [{from:'1', to:'2'}, {from:'2', to:'1'}] };
  expect(validate(g).ok).toBe(false); // duplicate in undirected
});
