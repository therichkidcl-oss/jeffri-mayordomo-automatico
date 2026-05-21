export async function listProjects() {
  const res = await fetch('/api/projects');
  return res.json();
}

export async function switchProject(displayName) {
  const res = await fetch('/api/switch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: displayName }),
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export async function capture() {
  const res = await fetch('/api/capture', { method: 'POST' });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export async function stopClaude() {
  const res = await fetch('/api/stop', { method: 'POST' });
  return res.json();
}
