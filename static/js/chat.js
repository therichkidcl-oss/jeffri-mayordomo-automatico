import { addJeffriMessage, addUserMessage, addSystemMessage } from './state.js';
import { sendUnified } from './api.js';

let ws = null;
let reconnectDelay = 1000;
const MAX_DELAY = 10000;

const attachments = [];  // Array of File objects

function renderAttachments() {
  const wrap = document.getElementById('attachments');
  wrap.replaceChildren();
  attachments.forEach((file, idx) => {
    const item = document.createElement('div');
    item.className = 'relative inline-block';
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    img.className = 'w-16 h-16 object-cover rounded border border-amber-700/40';
    const x = document.createElement('button');
    x.type = 'button';
    x.textContent = '×';
    x.className = 'absolute -top-1 -right-1 bg-red-700 rounded-full w-5 h-5 flex items-center justify-center text-xs';
    x.onclick = () => {
      URL.revokeObjectURL(img.src);
      attachments.splice(idx, 1);
      renderAttachments();
    };
    item.appendChild(img);
    item.appendChild(x);
    wrap.appendChild(item);
  });
}

function connect() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${window.location.host}/ws/chat`);

  ws.onopen = () => {
    addSystemMessage('🟢 Conectado a Jeffri');
    reconnectDelay = 1000;
  };
  ws.onmessage = (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch (e) { return; }
    handleServerMessage(data);
  };
  ws.onclose = () => {
    addSystemMessage(`🔴 Desconectado. Reintentando en ${reconnectDelay/1000}s...`);
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, MAX_DELAY);
  };
}

function handleServerMessage(data) {
  switch (data.type) {
    case 'welcome':
      addSystemMessage(data.message);
      if (window.batcaveShowSpeech) window.batcaveShowSpeech('Bienvenido, Sir Rich.');
      break;
    case 'confirm_enhanced': renderEnhancedConfirm(data); break;
    case 'confirm_destructive': renderDestructiveConfirm(data); break;
    case 'sent':
      addSystemMessage(`✉️ Enviado: ${data.text.slice(0, 80)}`);
      if (window.batcaveShowSpeech) window.batcaveShowSpeech('Entregado a Claude, senor.');
      break;
    case 'cancelled': addSystemMessage('❌ Cancelado'); break;
    case 'error': addSystemMessage(`❌ ${data.message}`); break;
  }
}

function makeButton(label, classes, onClick) {
  const btn = document.createElement('button');
  btn.textContent = label;
  btn.className = classes;
  btn.onclick = onClick;
  return btn;
}

function renderEnhancedConfirm(data) {
  const wrap = document.createElement('div');
  wrap.className = 'msg-jeffri';

  const orig = document.createElement('div');
  const ol = document.createElement('strong');
  ol.textContent = '📝 Original: ';
  orig.appendChild(ol);
  orig.appendChild(document.createTextNode(data.original));
  wrap.appendChild(orig);

  const enh = document.createElement('div');
  enh.className = 'mt-2';
  const el = document.createElement('strong');
  el.textContent = '✨ Mejorado: ';
  enh.appendChild(el);
  enh.appendChild(document.createTextNode(data.enhanced));
  wrap.appendChild(enh);

  const buttons = document.createElement('div');
  buttons.className = 'mt-2 flex gap-2';
  const send = (choice) => {
    ws.send(JSON.stringify({ type: 'confirm_response', token: data.token, choice }));
    buttons.querySelectorAll('button').forEach(b => b.disabled = true);
  };
  buttons.appendChild(makeButton('✅ Mejorado', 'btn-confirm-primary', () => send('send_enhanced')));
  buttons.appendChild(makeButton('📤 Original', 'btn-confirm-secondary', () => send('send_original')));
  buttons.appendChild(makeButton('❌ Cancelar', 'btn-confirm-cancel', () => send('cancel')));
  wrap.appendChild(buttons);

  document.getElementById('messages').appendChild(wrap);
  document.getElementById('messages').scrollTop = 99999;
}

function renderDestructiveConfirm(data) {
  const wrap = document.createElement('div');
  wrap.className = 'msg-jeffri';
  const t = document.createElement('div');
  const warn = document.createElement('strong');
  warn.textContent = '⚠️ Destructivo: ';
  t.appendChild(warn);
  t.appendChild(document.createTextNode(data.text));
  wrap.appendChild(t);

  const buttons = document.createElement('div');
  buttons.className = 'mt-2 flex gap-2';
  const send = (choice) => {
    ws.send(JSON.stringify({ type: 'confirm_response', token: data.token, choice }));
    buttons.querySelectorAll('button').forEach(b => b.disabled = true);
  };
  buttons.appendChild(makeButton('✅ Si, mandar', 'btn-confirm-primary', () => send('send_enhanced')));
  buttons.appendChild(makeButton('❌ Cancelar', 'btn-confirm-cancel', () => send('cancel')));
  wrap.appendChild(buttons);

  document.getElementById('messages').appendChild(wrap);
  document.getElementById('messages').scrollTop = 99999;
}

document.getElementById('btn-attach').onclick = () => {
  document.getElementById('file-picker').click();
};

document.getElementById('file-picker').onchange = (e) => {
  for (const file of e.target.files) {
    if (file.type.startsWith('image/')) attachments.push(file);
  }
  renderAttachments();
  e.target.value = '';
};

const chatForm = document.getElementById('chat-form');
chatForm.addEventListener('dragover', (e) => {
  e.preventDefault();
  chatForm.classList.add('ring', 'ring-amber-500');
});
chatForm.addEventListener('dragleave', () => {
  chatForm.classList.remove('ring', 'ring-amber-500');
});
chatForm.addEventListener('drop', (e) => {
  e.preventDefault();
  chatForm.classList.remove('ring', 'ring-amber-500');
  for (const file of e.dataTransfer.files) {
    if (file.type.startsWith('image/')) attachments.push(file);
  }
  renderAttachments();
});

document.getElementById('chat-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('chat-input');
  const text = input.value.trim();

  // Si hay attachments, usar el REST endpoint /api/send
  if (attachments.length > 0) {
    const filesToSend = attachments.slice();
    attachments.length = 0;
    input.value = '';
    renderAttachments();
    addUserMessage(`${text || '(sin texto)'} 🖼 +${filesToSend.length}`);
    try {
      await sendUnified(text, filesToSend);
      addSystemMessage(`🖼 Enviado: ${filesToSend.length} imagen(es)${text ? ' con texto' : ''}`);
    } catch (err) {
      addSystemMessage(`❌ ${err.message}`);
    }
    return;
  }

  // Sin attachments: ruta tradicional via WebSocket (con enhancer)
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
  addUserMessage(text);
  ws.send(JSON.stringify({ type: 'user_text', text }));
  input.value = '';
});

connect();

let eventsWs = null;

function connectEvents() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  eventsWs = new WebSocket(`${proto}//${window.location.host}/ws/events`);

  eventsWs.onmessage = (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch (e) { return; }
    if (data.type === 'claude_text') {
      addJeffriMessage(`🤖 ${data.text}`);
      if (window.batcaveShowSpeech) window.batcaveShowSpeech(data.text);
    } else if (data.type === 'claude_photo') {
      const wrap = document.createElement('div');
      wrap.className = 'msg-jeffri';
      const img = document.createElement('img');
      img.src = `data:image/png;base64,${data.png_b64}`;
      img.className = 'max-w-full rounded';
      wrap.appendChild(img);
      if (data.caption) {
        const cap = document.createElement('div');
        cap.textContent = data.caption;
        cap.className = 'text-xs mt-1 opacity-70';
        wrap.appendChild(cap);
      }
      const messages = document.getElementById('messages');
      messages.appendChild(wrap);
      messages.scrollTop = 99999;
    }
  };

  eventsWs.onclose = () => setTimeout(connectEvents, 2000);
}

connectEvents();
