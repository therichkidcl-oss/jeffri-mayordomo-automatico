import { listProjects, switchProject, capture, stopClaude } from './api.js';
import { addSystemMessage } from './state.js';

document.getElementById('btn-projects').onclick = async () => {
  try {
    const projects = await listProjects();
    showProjectPicker(projects);
  } catch (e) {
    addSystemMessage(`❌ ${e.message}`);
  }
};

document.getElementById('btn-capture').onclick = async () => {
  try {
    const data = await capture();
    const wrap = document.createElement('div');
    wrap.className = 'msg-jeffri';
    const img = document.createElement('img');
    img.src = `data:image/png;base64,${data.png_b64}`;
    img.className = 'max-w-full rounded';
    wrap.appendChild(img);
    const messages = document.getElementById('messages');
    messages.appendChild(wrap);
    messages.scrollTop = 99999;
  } catch (e) {
    addSystemMessage(`❌ ${e.message}`);
  }
};

document.getElementById('btn-stop').onclick = async () => {
  try {
    await stopClaude();
    addSystemMessage('⏹ ESC enviado a Claude');
  } catch (e) {
    addSystemMessage(`❌ ${e.message}`);
  }
};

function showProjectPicker(projects) {
  const modal = document.createElement('div');
  modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-50';

  const dialog = document.createElement('div');
  dialog.className = 'bg-slate-800 border border-amber-700 rounded p-6 max-w-md w-full max-h-[80vh] overflow-y-auto';

  const title = document.createElement('h2');
  title.className = 'text-xl font-bold mb-4';
  title.textContent = '📁 Proyectos';
  dialog.appendChild(title);

  const list = document.createElement('div');
  list.className = 'space-y-2';
  dialog.appendChild(list);

  projects.forEach(p => {
    const btn = document.createElement('button');
    btn.className = 'block w-full text-left bg-slate-700 hover:bg-slate-600 px-3 py-2 rounded';
    btn.textContent = `📁 ${p.display_name} · ${p.session_count}`;
    btn.onclick = async () => {
      modal.remove();
      try {
        await switchProject(p.display_name);
        addSystemMessage(`✅ Cambiado a ${p.display_name}`);
      } catch (e) {
        addSystemMessage(`❌ ${e.message}`);
      }
    };
    list.appendChild(btn);
  });

  const close = document.createElement('button');
  close.textContent = 'Cerrar';
  close.className = 'mt-4 bg-red-700 px-3 py-1 rounded';
  close.onclick = () => modal.remove();
  dialog.appendChild(close);

  modal.appendChild(dialog);
  document.body.appendChild(modal);
}
