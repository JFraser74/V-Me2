async function fetchTasks(){
  try{
    const r = await fetch('/ops/tasks');
    if(!r.ok) return [];
    return await r.json();
  }catch(e){ return []; }
}

function renderTasks(list){
  const tbody = document.getElementById('ops-tbody'); tbody.innerHTML='';
  (list||[]).slice(0,50).forEach(it => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${it.id}</td><td>${it.created_at||''}</td><td>${(it.title||'').replace(/</g,'&lt;')}</td><td>${it.status||''}</td>`;
    tr.onclick = () => { openStreamFor(it.id); };
    tbody.appendChild(tr);
  });
}

async function openStreamFor(id){
  const log = document.getElementById('ops-log'); log.textContent = '(opening...)\n';
  try{
    if (window.VM_ADMIN_UI === true){
      const r = await fetch('/ops/stream_tokens', { method: 'POST', headers: {'content-type':'application/json'}, body: JSON.stringify({task_id: id}) });
      if(r.ok){ const j = await r.json(); const tok = j.token; const src = new EventSource(`/ops/tasks/${id}/stream?token=${encodeURIComponent(tok)}`);
        src.onmessage = (e) => { try{ log.textContent += e.data + '\n'; log.scrollTop = log.scrollHeight; }catch(_){} };
        src.onerror = () => { src.close(); };
        return;
      }
    }
  }catch(e){ /* fallthrough */ }
  // fallback: open stream directly (may require legacy admin_token)
  const src = new EventSource(`/ops/tasks/${id}/stream`);
  src.onmessage = (e) => { try{ document.getElementById('ops-log').textContent += e.data + '\n'; document.getElementById('ops-log').scrollTop = document.getElementById('ops-log').scrollHeight; }catch(_){} };
  src.onerror = () => { src.close(); };
}

document.addEventListener('DOMContentLoaded', async ()=>{ const list = await fetchTasks(); renderTasks(list); });
