import { ThreadStore } from '../src/thread_store';

const store = new ThreadStore();

// Subscribe to changes
store.subscribe(() => {
  console.log(`Messages: ${store.length}`);
});

// Simulate a conversation
const userMsg = store.addMessage('user', 'Make this paragraph punchier');
console.log('User:', userMsg.content);

// Start streaming an assistant response
const assistantMsg = store.addMessage('assistant', '', 'streaming');
store.appendContent(assistantMsg.id, 'Here is a ');
store.appendContent(assistantMsg.id, 'punchier version.');
store.setStatus(assistantMsg.id, 'complete');

console.log('Assistant:', store.getMessage(assistantMsg.id)?.content);

// Get latest by role
const latest = store.getLatestByRole('assistant');
console.log('Latest assistant:', latest?.content);

// Clear the thread
store.clear();
console.log('After clear:', store.length);
