const AUTH_TOKEN = (() => {
  const url = new URLSearchParams(location.search).get('token');
  if (url) {
    localStorage.setItem('batcave_token', url);
    history.replaceState({}, '', location.pathname);
  }
  return localStorage.getItem('batcave_token') || '';
})();

function authHeaders(extra = {}) {
  const h = { ...extra };
  if (AUTH_TOKEN) h['X-Auth-Token'] = AUTH_TOKEN;
  return h;
}

export async function listProjects() {
  const res = await fetch('/api/projects', { headers: authHeaders() });
  return res.json();
}

export async function switchProject(displayName) {
  const res = await fetch('/api/switch', {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ display_name: displayName }),
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export async function capture() {
  const res = await fetch('/api/capture', { method: 'POST', headers: authHeaders() });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export async function stopClaude() {
  const res = await fetch('/api/stop', { method: 'POST', headers: authHeaders() });
  return res.json();
}
