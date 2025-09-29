(() => {
  const $ = (sel) => document.querySelector(sel);
  let currentSessionId = "";
  let messages = [];
    let namePromptShown = false; // only show inline name the first time a session is created

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

  function startAssistantBubble() {
    const wrap = document.querySelector("#history");
    const node = document.createElement('div');
    node.className = 'bubble assistant streaming';
    node.innerHTML = `<pre class="content"></pre><div class="dots">···</div>`;
    wrap.appendChild(node);
    wrap.scrollTop = wrap.scrollHeight;
    return node;
  }

  function appendPartial(node, chunk) {
    const pre = node.querySelector('.content');
    pre.textContent += chunk;
    const wrap = document.querySelector('#history'); wrap.scrollTop = wrap.scrollHeight;
  }

  function finalizeAssistant(node, fullText) {
    node.classList.remove('streaming');
    node.querySelector('.dots')?.remove();
    node.querySelector('.content').textContent = fullText;
  }

  async function sendMessageStreaming({ text, sessionId }) {
    appendUserBubble(text);
    const node = startAssistantBubble();
    let full = '';
    let newSessionId = sessionId || '';
    const qs = new URLSearchParams();
    if (sessionId) qs.set('session_id', sessionId);
    qs.set('message', text);
    const src = new EventSource(`/agent/stream?${qs.toString()}`);
    return new Promise((resolve, reject) => {
      const cleanup = () => { try { src.close(); } catch (e) {} };

      src.addEventListener('tick', (e) => {
        // heartbeat - ignore or use to animate
      });

      src.addEventListener('chunk', (e) => {
        try {
          const data = JSON.parse(e.data);
          const piece = data.text || '';
          full += piece;
          appendPartial(node, piece);
          if (data.session_id) newSessionId = data.session_id;
        } catch (_) {}
      });

        src.addEventListener('done', (e) => {
          try {
            const data = JSON.parse(e.data || '{}');
            if (data.text) full = data.text;
            if (data.session_id) newSessionId = data.session_id;
          } catch (_) {}
          finalizeAssistant(node, full);
          if (newSessionId && newSessionId !== currentSessionId) {
            currentSessionId = newSessionId;
            if (!namePromptShown) { try { showInlineName(); } catch(e){} namePromptShown = true; }
          }
          cleanup();
          resolve({ text: full, sessionId: newSessionId });
        });

      src.addEventListener('error', (e) => {
        cleanup();
        reject(e);
      });
    });
  }

  function appendUserBubble(text){
    const wrap = document.querySelector('#history');
    const node = document.createElement('div'); node.className = 'bubble user'; node.textContent = text || '';
    wrap.appendChild(node); wrap.scrollTop = wrap.scrollHeight;
  }

  function appendAssistantBubble(text){
    const wrap = document.querySelector('#history');
    const node = document.createElement('div'); node.className = 'bubble assistant'; node.textContent = text || '';
    wrap.appendChild(node); wrap.scrollTop = wrap.scrollHeight;
  }

  async function sendMessage(){
    // stop any dictation before reading the composer to avoid mid-send edits
    try { if (typeof stopDictation === 'function') stopDictation(true); } catch(e){}
    const input = $('#composer-input'); const text = (input.value || '').trim(); if(!text) return;
    setComposerBusy && setComposerBusy(true);
    try {
      // prefer SSE streaming path
      await sendMessageStreaming({ text, sessionId: currentSessionId });
    } catch (err) {
      // fallback to one-shot POST
      const body = { message: text };
      if (currentSessionId) body.session_id = currentSessionId;
      try {
        const res = await fetch('/agent/chat', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
        const j = await res.json();
        appendUserBubble(text);
        appendAssistantBubble(j.text || j.message || '');
        if (j.session_id && j.session_id !== currentSessionId) {
          currentSessionId = String(j.session_id);
          if (!namePromptShown) { try { showInlineName(); } catch(e){} namePromptShown = true; }
        }
      } catch (e) {
        appendAssistantBubble('(error)');
      }
    } finally {
      try { input.value = ''; } catch(e){}
      // maintain compatibility with existing stop hook
      try { if (typeof stopDictationIfActive === 'function') stopDictationIfActive(); } catch(e){}
      setComposerBusy && setComposerBusy(false);
      await refreshRecent();
    }
  }

  // Save & Name (C5)
  async function saveOrRenameThread(title){
    title = (title||'').trim(); if(!title) return;
    try{
      if(!currentSessionId){
        const res = await fetch('/api/threads',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({title})});
        const data = await res.json(); if(data && data.id) currentSessionId = String(data.id);
      }else{
        await fetch(`/api/threads/${encodeURIComponent(currentSessionId)}/title`,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({title})});
      }
      await loadRecent();
    }catch(e){ console.warn('save/rename failed', e); }
  }
  function showInlineName(){ document.querySelector('#name-inline')?.classList.remove('hidden'); document.querySelector('#name-input')?.focus(); }
  function hideInlineName(){ document.querySelector('#name-inline')?.classList.add('hidden'); }
  function newChat(){ currentSessionId=''; messages = []; render(); try{ document.querySelector('#composer-input').value = ''; }catch(e){} hideInlineName(); namePromptShown = false; refreshRecent(); }
  async function loadRecent(){
    try{ const res = await fetch('/api/threads?limit=20'); const data = await res.json(); renderRecent(Array.isArray(data)?data:(data.items||[])); }catch(e){}
  }

  function init(){
    $('#btnNew').onclick = () => { newChat(); };
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
  $('#send-btn').onclick = () => { sendMessage(); };
  $('#attach-btn').onclick = () => { alert('Document upload is not yet enabled'); };
  // Mic placeholder toggle
  let micOn = false; $('#mic-btn').onclick = () => { micOn = !micOn; $('#mic-btn').textContent = micOn ? '🎙️•' : '🎙️'; };

    refreshRecent(); render();
  }
  // Savebar inline controls
  $('#save-btn').onclick = () => { showInlineName(); };
  $('#name-save-btn').onclick = async () => {
    const v = document.querySelector('#name-input')?.value || '';
    await saveOrRenameThread(v);
    hideInlineName();
  };
  $('#name-cancel-btn').onclick = () => { hideInlineName(); };
  document.querySelector('#name-input')?.addEventListener('keydown', async (ev) => {
    if(ev.key === 'Enter') { ev.preventDefault(); $('#name-save-btn').click(); }
    if(ev.key === 'Escape') { ev.preventDefault(); hideInlineName(); }
  });

  window.initCodingPanel = init;
  document.addEventListener('DOMContentLoaded', ()=>{ try{ init(); }catch(e){} });
})();
