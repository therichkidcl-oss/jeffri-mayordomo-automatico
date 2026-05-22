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
  modal.className = 'fixed inset-0 flex items-center justify-center z-50';
  modal.style.background = 'rgba(0, 0, 0, 0.85)';

  const dialog = document.createElement('div');
  dialog.className = 'rounded-lg p-6 max-w-md w-full max-h-[80vh] overflow-y-auto';
  dialog.style.background = 'linear-gradient(180deg, #141414 0%, #0f0f0f 100%)';
  dialog.style.border = '1px solid #f97316';
  dialog.style.boxShadow = '0 8px 32px rgba(249, 115, 22, 0.2)';

  const title = document.createElement('h2');
  title.className = 'text-xl font-bold mb-4';
  title.style.color = '#f97316';
  title.textContent = '📁 Proyectos';
  dialog.appendChild(title);

  const list = document.createElement('div');
  list.className = 'space-y-2';
  dialog.appendChild(list);

  projects.forEach(p => {
    const btn = document.createElement('button');
    btn.className = 'block w-full text-left px-3 py-2 rounded transition-colors';
    btn.style.background = '#1a1a1a';
    btn.style.border = '1px solid #404040';
    btn.style.color = '#fafafa';
    btn.onmouseover = () => {
      btn.style.background = '#2a1305';
      btn.style.borderColor = '#f97316';
    };
    btn.onmouseout = () => {
      btn.style.background = '#1a1a1a';
      btn.style.borderColor = '#404040';
    };
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
  close.className = 'mt-4 px-4 py-1.5 rounded font-bold transition-all';
  close.style.background = '#1a0606';
  close.style.color = '#fca5a5';
  close.style.border = '1px solid #7f1d1d';
  close.onmouseover = () => {
    close.style.background = '#dc2626';
    close.style.color = '#fafafa';
  };
  close.onmouseout = () => {
    close.style.background = '#1a0606';
    close.style.color = '#fca5a5';
  };
  close.onclick = () => modal.remove();
  dialog.appendChild(close);

  modal.appendChild(dialog);
  document.body.appendChild(modal);
}
