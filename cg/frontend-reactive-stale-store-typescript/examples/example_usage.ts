import { ReactiveGraphStore } from '../src/reactive_stale_store';
import { Node, Edge } from '../src/graph';

async function main() {
  const store = new ReactiveGraphStore();
  store.subscribe(() => {
    console.log("Store updated, stale nodes:", Array.from(store.staleNodes));
  });

  const n1: Node = { id: "1" };
  const n2: Node = { id: "2" };
  const e: Edge = { from: "1", to: "2" };

  store.addNode(n1);
  store.addNode(n2);
  store.addEdge(e);

  store.updateNode("1", { tags: ["updated"] });
}

main().catch(console.error);
