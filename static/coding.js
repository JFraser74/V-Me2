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

  // Delegate to Agent (Planner hand-off)
  async function delegateToAgent(){
    try{ if (typeof stopDictation === 'function') { try{ stopDictation(true); }catch(_){} } }catch(e){}
    const input = document.getElementById('composer-input');
    const body = (input?.value || '').trim() || '(no body)';
    const title = prompt('Task title?'); if (!title) return;
    try{
      const r = await fetch('/agent/plan', { method: 'POST', headers: {'content-type':'application/json'}, body: JSON.stringify({ title, body }) });
      if(!r.ok){ alert('Failed to create task'); return; }
      const data = await r.json();
      if (data && data.task_id){
        openOpsLogViewer(data.task_id, document.querySelector('#ops-log-container'));
      }
    }catch(e){ alert('Failed to create task'); }
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
    const btnDel = $('#btnDelegate');
    if (btnDel) btnDel.onclick = delegateToAgent;
    const btnOps = $('#btnNewOps');
    if (btnOps) btnOps.onclick = async () => {
      const title = prompt('Task title') || '';
      if (!title) return;
      const body = prompt('Task body/notes (optional)') || '';
      try{
        const j = await window.createOpsTask(title, body);
        const container = document.querySelector('#ops-log-container');
        window.openOpsLogViewer(j.id, container);
      }catch(e){ alert('Failed creating task'); }
    };
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
  // Dictation state & utilities (C4)
  let dictationActive = false;
  let recognition = null;

  function isDictationSupported(){ return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window; }
  function getSpeechRecognitionCtor(){ return window.SpeechRecognition || window.webkitSpeechRecognition; }

  async function startDictation(){
    if (dictationActive) return;
    if (!isDictationSupported()){ alert('Dictation is not available in this browser yet.'); return; }
    const SR = getSpeechRecognitionCtor();
    recognition = new SR();
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.continuous = true;

    const input = document.querySelector('#composer-input');
    const micBtn = document.querySelector('#mic-btn');
    micBtn.classList.add('active');
    document.querySelector('#mic-hint')?.classList.remove('hidden');
    dictationActive = true;

    let finalText = input.value || '';

    recognition.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++){
        const chunk = e.results[i][0].transcript;
        if (e.results[i].isFinal){ finalText += (finalText && !finalText.endsWith(' ') ? ' ' : '') + chunk; }
        else { interim += chunk; }
      }
      input.value = finalText + (interim ? ' ' + interim : '');
    };
    recognition.onerror = () => stopDictation(true);
    recognition.onend = () => stopDictation(true);
    try{ recognition.start(); }catch(e){ /* ignore start errors */ }
  }

  function stopDictation(silent=false){
    if (!dictationActive) return;
    dictationActive = false;
    try{ recognition && recognition.stop(); }catch(e){}
    recognition = null;
    document.querySelector('#mic-btn')?.classList.remove('active');
    document.querySelector('#mic-hint')?.classList.add('hidden');
    if (!silent) console.debug('Dictation stopped');
  }

  // Wire the mic button to toggle dictation
  document.addEventListener('DOMContentLoaded', ()=>{
    const mic = document.querySelector('#mic-btn');
    if (mic){ mic.addEventListener('click', ()=>{ if (dictationActive) stopDictation(); else startDictation(); }); }
  });

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

// Minimal Ops UI hooks
(function(){
  async function createOpsTask(title, body){
    const token = localStorage.getItem('ADMIN_TOKEN') || '';
    const res = await fetch('/ops/tasks', {method:'POST', headers: {'content-type':'application/json', 'X-Admin-Token': token}, body: JSON.stringify({title, body})});
    if(!res.ok) throw new Error('failed');
    return await res.json();
  }

  function openOpsLogViewer(taskId, container){
    container.innerHTML = '';
    const pre = document.createElement('div'); pre.className = 'ops-log'; container.appendChild(pre);
    async function _openWithToken(){
      try{
        // if admin UI proxy or flag present, request a token first
        if (window.VM_ADMIN_UI === true) {
          const r = await fetch('/ops/stream_tokens', { method: 'POST', headers: {'content-type':'application/json'}, body: JSON.stringify({task_id: taskId}) });
          if (r.ok){ const j = await r.json(); const token = j.token; const src = new EventSource(`/ops/tasks/${taskId}/stream?token=${encodeURIComponent(token)}`);
            src.onmessage = (e) => { try{ const d = JSON.parse(e.data); pre.textContent += JSON.stringify(d) + '\n'; pre.scrollTop = pre.scrollHeight; }catch(_){} };
            src.onerror = ()=>{ src.close(); };
            return src;
          }
        }
      }catch(e){ /* fallthrough to legacy */ }
      // legacy fallback (uses admin_token via localStorage or query)
      const src = new EventSource(`/ops/tasks/${taskId}/stream`);
      src.onmessage = (e) => { try{ const d = JSON.parse(e.data); pre.textContent += JSON.stringify(d) + '\n'; pre.scrollTop = pre.scrollHeight; }catch(_){} };
      src.onerror = ()=>{ src.close(); };
      return src;
    }
    _openWithToken();
    return { close: ()=>{} };
  }

  // Expose for test hooks
  window.createOpsTask = createOpsTask;
  window.openOpsLogViewer = openOpsLogViewer;
})();
