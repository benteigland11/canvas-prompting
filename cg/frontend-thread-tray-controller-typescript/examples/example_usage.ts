import { ThreadTrayController } from '../src/thread_tray_controller';
import type { TrayStore, TrayMessage, MessageRole, MessageStatus } from '../src/thread_tray_controller';

// Simple in-memory store factory
function createStore(): TrayStore {
  let messages: TrayMessage[] = [];
  let idCounter = 0;
  return {
    addMessage(role: MessageRole, content = '', status: MessageStatus = 'complete') {
      idCounter += 1;
      const msg: TrayMessage = { id: `msg_${idCounter}`, role, content, status };
      messages = [...messages, msg];
      return msg;
    },
    appendContent(id: string, chunk: string) {
      const idx = messages.findIndex(m => m.id === id);
      if (idx === -1) throw new Error(`Unknown id: ${id}`);
      const updated = { ...messages[idx], content: messages[idx].content + chunk };
      messages = messages.map(m => m.id === id ? updated : m);
      return updated;
    },
    setStatus(id: string, status: MessageStatus) {
      const idx = messages.findIndex(m => m.id === id);
      if (idx === -1) throw new Error(`Unknown id: ${id}`);
      const updated = { ...messages[idx], status };
      messages = messages.map(m => m.id === id ? updated : m);
      return updated;
    },
    getMessages: () => messages,
    getLatestByRole(role: MessageRole) {
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === role) return messages[i];
      }
      return undefined;
    },
    clear() { messages = []; },
  };
}

// Create the controller
const controller = new ThreadTrayController({ createStore });

// Listen for state changes
controller.subscribe(state => console.log('State:', state));

// Open the tray for a card
controller.open('card-42', 'This is the current card content.');
console.log('Card ID:', controller.getCardId());

// Simulate a conversation in the tray
const store = controller.getStore()!;
store.addMessage('user', 'Make it more concise');
store.addMessage('assistant', 'Concise card content.', 'complete');

// Commit the result back to the card
const payload = controller.commit();
console.log('Commit payload:', JSON.stringify(payload));
// → { cardId: "card-42", content: "Concise card content." }
// Controller auto-closes after commit
console.log('Final state:', controller.getState());
