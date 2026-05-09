import { SessionStateStore } from '../src/session_state_store';

async function main() {
  const store = new SessionStateStore<{ user: string }>();
  
  store.subscribe(() => {
    console.log("State changed:", store.state);
  });

  await store.runAsync(Promise.resolve({ user: "Alice" }));
}

main().catch(console.error);
