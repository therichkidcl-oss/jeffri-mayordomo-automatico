const statusEl = document.getElementById('status');
const messagesEl = document.getElementById('messages');

async function fetchState() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();
    statusEl.textContent = `Conectado. Enhancer ${data.enhancer_enabled ? 'ON' : 'OFF'}.`;
    addSystemMessage('🦇 Batcave operativa, senor.');
  } catch (e) {
    statusEl.textContent = 'Sin conexion';
    addSystemMessage('Sin conexion al backend.');
  }
}

export function addSystemMessage(text) {
  const div = document.createElement('div');
  div.className = 'msg-system';
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

export function addUserMessage(text) {
  const div = document.createElement('div');
  div.className = 'msg-user';
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

export function addJeffriMessage(text) {
  const div = document.createElement('div');
  div.className = 'msg-jeffri';
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

fetchState();
