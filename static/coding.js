(() => {
  const $ = (sel) => document.querySelector(sel);
  let currentSessionId = "";
  let messages = [];

  function renderRecent(items){
    const el = $('#recentList'); el.innerHTML = '';
    (items||[]).forEach(it => {
      const d = document.createElement('div'); d.className = 'recent-item'; d.textContent = it.title || ('id:'+it.id);
      d.onclick = async () => { currentSessionId = String(it.id); await loadThread(it.id); render(); };
      el.appendChild(d);
    });
  }

  async function fetchRecent(){
    try{
      const r = await fetch('/api/threads?limit=20'); if(!r.ok) throw r;
      const j = await r.json(); return j.items || [];
    }catch(e){ return []; }
  }

  async function loadThread(id){
    try{
      const r = await fetch(`/api/threads/${id}/messages`); if(!r.ok) throw r;
      const j = await r.json(); messages = j.items || [];
    }catch(e){ messages = []; }
  }

  function render(){
    const hist = $('#history'); hist.innerHTML = '';
    messages.forEach(m => {
      const b = document.createElement('div'); b.className = 'bubble ' + (m.role==='user' ? 'user':'assistant'); b.textContent = m.content || m.text || '';
      hist.appendChild(b);
    });
    $('#composer-input').value = '';
  }

  async function refreshRecent(){
    const items = await fetchRecent(); renderRecent(items);
  }

  async function sendMessage(){
    const ta = $('#composer-input'); const txt = ta.value.trim(); if(!txt) return;
    // push user bubble immediately
    messages.push({role:'user', content: txt}); render();
    // call server
    const payload = {message: txt}; if(currentSessionId) payload.session_id = currentSessionId;
    try{
      const r = await fetch('/agent/chat', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(payload)});
      if(!r.ok){ throw r; }
      const j = await r.json();
      // append assistant
      messages.push({role:'assistant', content: j.text || j.message || ''});
      if(j.session_id) currentSessionId = String(j.session_id);
      render();
      await refreshRecent();
    }catch(e){ messages.push({role:'assistant', content: '(error)'}); render(); }
  }

  function init(){
    $('#btnNew').onclick = () => { currentSessionId=''; messages = []; render(); };
    $('#btnSaveName').onclick = async () => {
      const title = prompt('Enter a title for this thread') || '';
      if(!title) return;
      try{
        if(!currentSessionId){
          const r = await fetch('/api/threads', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({label: title})});
          const j = await r.json(); currentSessionId = String(j.id || j.session || j.id || '');
        } else {
          await fetch(`/api/threads/${currentSessionId}/title?title=${encodeURIComponent(title)}`, {method:'PUT'});
        }
      }catch(e){}
      await refreshRecent();
    };
    $('#btnSend').onclick = () => { sendMessage(); };
    $('#btnAttach').onclick = () => { alert('Document upload is not yet enabled'); };
    // Mic placeholder toggle
    let micOn = false; $('#btnMic').onclick = () => { micOn = !micOn; $('#btnMic').textContent = micOn ? '🎙️•' : '🎙️'; };

    refreshRecent(); render();
  }

  window.initCodingPanel = init;
  document.addEventListener('DOMContentLoaded', ()=>{ try{ init(); }catch(e){} });
})();
