import { addJeffriMessage, addUserMessage, addSystemMessage } from './state.js';

let ws = null;
let reconnectDelay = 1000;
const MAX_DELAY = 10000;

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
  buttons.appendChild(makeButton('✅ Mejorado', 'bg-green-700 hover:bg-green-600 px-2 py-1 rounded text-xs', () => send('send_enhanced')));
  buttons.appendChild(makeButton('📤 Original', 'bg-blue-700 hover:bg-blue-600 px-2 py-1 rounded text-xs', () => send('send_original')));
  buttons.appendChild(makeButton('❌ Cancelar', 'bg-red-700 hover:bg-red-600 px-2 py-1 rounded text-xs', () => send('cancel')));
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
  buttons.appendChild(makeButton('✅ Si, mandar', 'bg-green-700 px-2 py-1 rounded text-xs', () => send('send_enhanced')));
  buttons.appendChild(makeButton('❌ Cancelar', 'bg-red-700 px-2 py-1 rounded text-xs', () => send('cancel')));
  wrap.appendChild(buttons);

  document.getElementById('messages').appendChild(wrap);
  document.getElementById('messages').scrollTop = 99999;
}

document.getElementById('chat-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
  addUserMessage(text);
  ws.send(JSON.stringify({ type: 'user_text', text }));
  input.value = '';
});

connect();
