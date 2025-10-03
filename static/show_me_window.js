(function(){
  const $ = (sel) => document.querySelector(sel);
  let nextNewSession = false;
  let currentSessionId = null;

  const setStatus = (t) => { $('#status') && ($('#status').textContent = t || ''); };
  const log = (t) => { const el=$('#log'); if(!el) return; el.textContent += (t + "\n"); el.scrollTop = el.scrollHeight; };
  const pill = (id) => { const el=$('#session-pill'); if(el) el.textContent = 'session: ' + (id || 'n/a'); };
  const setLangPill = (v) => { const el=$('#langgraph-pill'); if(!el) return; el.textContent = 'LangGraph: ' + (v ? 'enabled' : 'disabled'); el.style.background = v ? '#133' : '#311'; };
  const setSettingsBanner = (text, warn) => { const el=$('#settingsBanner'); if(!el) return; el.textContent = text || ''; el.style.color = warn ? 'orange' : ''; };

  // Monaco editor integration (load from CDN on demand)
  let monacoEditor = null;
  async function loadMonaco() {
    if (monacoEditor) return monacoEditor;
    if (!window.require) {
      const s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/require.js/2.3.6/require.min.js';
      document.head.appendChild(s);
      await new Promise(r => s.onload = r);
    }
    return new Promise((resolve, reject) => {
      try {
        window.require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.39.0/min/vs' } });
        window.require(['vs/editor/editor.main'], () => {
          const container = document.getElementById('codeArea') || document.getElementById('codeAreaContainer');
          if (!container) { resolve(null); return; }
          const ed = monaco.editor.create(container, { value: '', language: 'plaintext', automaticLayout: true, wordWrap: 'off' });
          monacoEditor = ed;
          resolve(ed);
        });
      } catch (e) { resolve(null); }
    });
  }

  // Modes (placeholders + working ones)
  const modePanel = $('#modePanel');
  function setModeText(m){
    modePanel && (modePanel.innerHTML = ({
      Chat: 'Chat mode. Type messages or slash commands (e.g., <code>/ls .</code>, <code>/read main.py</code>).',
      Email: `
        <div style="display:flex;gap:12px">
          <div style="flex:1 1 360px;max-width:420px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
              <div style="font-weight:700">Mail</div>
              <div style="display:flex;gap:8px"><input id="emailSearch" placeholder="Search mail" style="width:220px"/><button id="emailSearchBtn">Search</button></div>
            </div>
            <div id="emailList" class="list" style="background:#0f1115;border:1px solid #232530;border-radius:8px;padding:8px;height:420px;overflow:auto"></div>
          </div>
          <div style="flex:2 1 600px;display:flex;flex-direction:column;gap:8px">
            <div id="emailViewer" style="background:#0f1115;border:1px solid #232530;border-radius:8px;padding:12px;min-height:220px;overflow:auto">Select a message to view</div>
            <div id="emailCompose" style="background:#0f1115;border:1px solid #232530;border-radius:8px;padding:12px">
              <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><input id="composeTo" placeholder="To" style="flex:1"/><input id="composeSubject" placeholder="Subject" style="flex:2"/></div>
              <!-- Gmail-like toolbar: bold, italic, list -->
              <div id="composeToolbar" style="display:flex;gap:6px;align-items:center;margin-bottom:8px">
                <button class="tab tb-btn" id="tbBold" title="Bold (Ctrl/Cmd+B)" style="padding:6px;font-weight:700">B</button>
                <button class="tab tb-btn" id="tbItalic" title="Italic (Ctrl/Cmd+I)" style="padding:6px;font-style:italic">I</button>
                <button class="tab tb-btn" id="tbList" title="Bullet list" style="padding:6px">• List</button>
                <div style="flex:1"></div>
                <div class="muted" style="font-size:13px">Formatting: <span style="color:#9aa1ac">rich text</span></div>
              </div>
              <div contenteditable id="composeBody" style="min-height:160px;border:1px solid #232530;border-radius:6px;padding:8px;background:#0b0b0d"></div>
              <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:8px"><button id="composeSend">Send</button><button id="composeQueue">Queue</button></div>
            </div>
          </div>
        </div>
      `,
      Coding: `
        <div class="row" style="margin:.3rem 0">
          <input id="codePath" placeholder="path (e.g., main.py)" style="min-width:260px"/>
          <button id="btnRead">Read</button>
        </div>
        <textarea id="codeArea" placeholder="// file content here"></textarea>
        <div class="row" style="margin:.3rem 0">
          <button id="btnPreview">Preview Save</button>
          <button id="btnSave">Save (confirm)</button>
          <span class="muted" id="codeStatus"></span>
        </div>
      `,
      Supabase: 'Use the left panel Select to run <code>/agent/select</code> (read-only).',
      Docs: 'PLACEHOLDER — Document processing & tagging.',
      Schedule: 'PLACEHOLDER — Gantt/Calendar/Table views.',
      Budget: 'PLACEHOLDER — Spreadsheet totals & alerts.',
      PDF: `
        <div class="row" style="margin:.3rem 0">
          <input id="pdfUrl" class="wide-input" placeholder="remote PDF URL (optional)"/>
          <button id="btnLoadPdf">Load</button>
        </div>
        <input id="pdfFile" type="file" accept="application/pdf"/>
        <div style="height:8px"></div>
        <iframe id="pdfFrame" style="width:100%;height:480px;border:1px solid #232530;border-radius:10px;background:#111"></iframe>
      `,
      Earth: 'PLACEHOLDER — Load KMZ from Supabase; view via API.',
    })[m] || '…');

    // wire Coding controls if present
    const readBtn = $('#btnRead');
    const prevBtn = $('#btnPreview');
    const saveBtn = $('#btnSave');
    const codePath = $('#codePath');
    const codeArea = $('#codeArea');
    const codeStatus = $('#codeStatus');

    if (readBtn) readBtn.onclick = async () => {
      const path = codePath.value.trim(); if (!path) return;
      codeStatus.textContent = 'reading…';
      try {
        const r = await fetch('/agent/read', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({path})});
        const data = await r.json();
        if (data.ok) { codeArea.value = data.content || ''; codeStatus.textContent = 'loaded'; }
        else { codeStatus.textContent = data.error || 'read failed'; }
      } catch(e){ codeStatus.textContent = 'error'; log('[read error] '+e); }
    };
    
    // Try to initialize Monaco editor if present (async)
    (async ()=>{
      const mon = await loadMonaco();
      if (mon) {
        const ta = document.getElementById('codeArea');
        if (ta) {
          const wrap = document.createElement('div'); wrap.id = 'codeAreaContainer'; wrap.style.height = '300px'; ta.parentNode.replaceChild(wrap, ta);
          mon.setValue(codeArea.value || '');
        }
      }
    })();
    async function write(confirm){
      const path = codePath.value.trim(); if(!path) return;
      codeStatus.textContent = confirm ? 'saving…' : 'previewing…';
      try{
        const r = await fetch('/agent/write', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({path, content: codeArea.value, confirm})});
        const data = await r.json();
        if (data.ok && confirm) codeStatus.textContent = `saved ${data.bytes} bytes`;
        else if (data.ok && data.dry_run) codeStatus.textContent = data.note;
        else codeStatus.textContent = data.error || 'write failed';
      }catch(e){ codeStatus.textContent = 'error'; log('[write error] '+e); }
    }
    if (prevBtn) prevBtn.onclick = ()=>write(false);
    if (saveBtn) saveBtn.onclick = ()=>write(true);

    // Dirty state handling
    let dirty = false;
    function markDirty(v) { dirty = v; window.onbeforeunload = v ? function(){ return 'Unsaved changes'; } : null; }
    // Monitor monaco or textarea
    setInterval(()=>{
      try{
        const cur = monacoEditor ? monacoEditor.getValue() : (codeArea ? codeArea.value : '');
        if (cur !== (codeArea._last || '')) { markDirty(true); }
      }catch(e){}
    }, 800);
    // After successful save, clear dirty when confirmed
    const prevWrite = write;
    write = async function(confirm){
      const res = await prevWrite(confirm);
      try{
        if (res && res.ok && confirm) { markDirty(false); }
      }catch(e){}
      return res;
    };

    // wire PDF controls if present
    const pdfFrame = $('#pdfFrame');
    const btnLoadPdf = $('#btnLoadPdf');
    const pdfUrl = $('#pdfUrl');
    const pdfFile = $('#pdfFile');
    if (btnLoadPdf && pdfFrame) btnLoadPdf.onclick = ()=>{ if(pdfUrl.value.trim()) pdfFrame.src = pdfUrl.value.trim(); };
    if (pdfFile && pdfFrame) pdfFile.onchange = () => {
      const f = pdfFile.files && pdfFile.files[0]; if(!f) return;
      const url = URL.createObjectURL(f); pdfFrame.src = url;
    };
    // Show or hide chat-mode quick actions
    try{
      const actions = document.getElementById('chatModeActions');
      if (actions) { actions.style.display = (m === 'Chat') ? 'flex' : 'none'; }
    }catch(e){}

  // Email mode wiring
    if (m === 'Email') {
      // load initial list
      async function loadEmailList(q){
        try{
          const url = '/api/email/search' + (q ? ('?q='+encodeURIComponent(q)) : '');
          const r = await fetch(url);
          const j = await r.json();
          const list = j.items || [];
          const el = document.getElementById('emailList'); if(!el) return;
          el.innerHTML = list.map(it => (`<div class="row" style="border-bottom:1px solid #16161a;padding:8px;align-items:center;justify-content:space-between"><div style="flex:1"><div style="font-weight:600">${it.sender}</div><div style="color:#9aa1ac;font-size:13px">${it.subject}</div></div><div style="width:120px;text-align:right"><span class="muted">${new Date(it.date).toLocaleString()}</span>${it.has_attachments? ' 📎':''}<div><a href="#" data-id="${it.id}" class="openMail">Open</a> • <a href="${it.gmsg_link}" target="_blank">Gmail</a></div></div></div>`)).join('');
          // wire open handlers
          document.querySelectorAll('#emailList .openMail').forEach(a=>a.onclick = async (e)=>{ e.preventDefault(); const id = a.getAttribute('data-id'); const r2 = await fetch('/api/email/message/'+encodeURIComponent(id)); const j2 = await r2.json(); if (j2 && j2.html) document.getElementById('emailViewer').innerHTML = j2.html; });
        }catch(e){ console.warn('email load failed', e); }
      }
      // search wiring
      const sbtn = document.getElementById('emailSearchBtn'); if (sbtn) sbtn.onclick = ()=> loadEmailList(document.getElementById('emailSearch').value || '');
      const sin = document.getElementById('emailSearch'); if (sin) sin.addEventListener('keydown', (ev)=>{ if(ev.key==='Enter'){ ev.preventDefault(); loadEmailList(sin.value||''); }});
      // compose wiring
      const sendBtn = document.getElementById('composeSend'); if (sendBtn) sendBtn.onclick = async ()=>{
        const toEl = document.getElementById('composeTo'); const subjEl = document.getElementById('composeSubject'); const bodyEl = document.getElementById('composeBody');
        const to = toEl ? toEl.value || '' : ''; const subj = subjEl ? subjEl.value || '' : ''; const body = bodyEl ? bodyEl.innerHTML || '' : '';
        try{
          // sanitize HTML and create plain-text fallback
          const rawHtml = body || '';
          const sanitized = sanitizeHtml(rawHtml);
          const plain = (function(x){ const temp = document.createElement('div'); temp.innerHTML = x; return temp.innerText || temp.textContent || ''; })(sanitized);
          const payload = { to, subject: subj, body_html: sanitized, body_text: plain };
          const r = await fetch('/api/email/send', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(payload)});
          const j = await r.json(); if (j && j.ok){ alert('Queued to send (task '+(j.task_id||'')+')'); document.getElementById('composeBody').innerHTML=''; }
        }catch(e){ alert('send failed: '+e); }
      };
      const qbtn = document.getElementById('composeQueue'); if (qbtn) qbtn.onclick = ()=> alert('Queued (local)');

      // Toolbar wiring: execCommand fallback for basic formatting
      const tbBold = document.getElementById('tbBold');
      const tbItalic = document.getElementById('tbItalic');
      const tbList = document.getElementById('tbList');
      if (tbBold) tbBold.onclick = (e)=> { document.execCommand('bold'); document.getElementById('composeBody').focus(); tbBold.classList.toggle('active'); };
      if (tbItalic) tbItalic.onclick = (e)=> { document.execCommand('italic'); document.getElementById('composeBody').focus(); tbItalic.classList.toggle('active'); };
      if (tbList) tbList.onclick = (e)=> { document.execCommand('insertUnorderedList'); document.getElementById('composeBody').focus(); tbList.classList.toggle('active'); };

      // Add a small sanitize helper to allow a safe subset of tags
      function sanitizeHtml(dirty) {
        if (!dirty) return '';
        // Create element and remove dangerous nodes/attributes
        const doc = document.createElement('div');
        doc.innerHTML = dirty;
        const whitelist = ['B','STRONG','I','EM','U','UL','OL','LI','P','BR','A'];
        const walk = (node)=>{
          for (let i = node.childNodes.length - 1; i >= 0; i--) {
            const child = node.childNodes[i];
            if (child.nodeType === Node.ELEMENT_NODE) {
              if (!whitelist.includes(child.nodeName)) {
                // replace element with its children (strip tag)
                while (child.firstChild) node.insertBefore(child.firstChild, child);
                node.removeChild(child);
              } else {
                // allowed tag: sanitize attributes
                // only allow href on A and ensure no javascript: URIs
                if (child.nodeName === 'A') {
                  const href = child.getAttribute('href');
                  if (href && href.trim().toLowerCase().startsWith('javascript:')) { child.removeAttribute('href'); }
                } else {
                  // remove all attributes on non-A tags
                  [...child.attributes].forEach(attr => child.removeAttribute(attr.name));
                }
                walk(child);
              }
            } else if (child.nodeType === Node.TEXT_NODE) {
              // leave text nodes
            } else {
              // remove comments, etc
              node.removeChild(child);
            }
          }
        };
        walk(doc);
        return doc.innerHTML;
      }

      // Keyboard shortcuts (Ctrl/Cmd+B and Ctrl/Cmd+I) when focus is in composeBody
      const composeBodyEl = document.getElementById('composeBody');
      if (composeBodyEl) {
        composeBodyEl.addEventListener('keydown', (ev)=>{
          const meta = ev.ctrlKey || ev.metaKey;
          if (!meta) return;
          if (ev.key.toLowerCase() === 'b') { ev.preventDefault(); document.execCommand('bold'); }
          if (ev.key.toLowerCase() === 'i') { ev.preventDefault(); document.execCommand('italic'); }
        });
      }
      // initial load
      loadEmailList('');
    }
  }
  document.querySelectorAll('#modes .tab').forEach(btn=>{
    btn.onclick = () => {
      document.querySelectorAll('#modes .tab').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      setModeText(btn.dataset.mode);
    };
  });

  // Wire Show-Me Chat-mode quick actions (mirror the coding panel actions)
  const btnNewInShowMe = $('#btnNewInShowMe');
  const btnNewOpsInShowMe = $('#btnNewOpsInShowMe');
  const btnDelegateInShowMe = $('#btnDelegateInShowMe');
  if (btnNewInShowMe) btnNewInShowMe.onclick = () => { nextNewSession = true; const b = document.getElementById('newSessionBtn'); if (b) b.textContent = 'Will start new session on next send'; try{ document.getElementById('msg')?.focus(); }catch(e){} };
  if (btnNewOpsInShowMe) btnNewOpsInShowMe.onclick = async () => {
    const title = prompt('Task title') || '';
    if (!title) return;
    const body = prompt('Task body/notes (optional)') || '';
    try{
      const token = localStorage.getItem('ADMIN_TOKEN') || '';
      const res = await fetch('/ops/tasks', {method:'POST', headers: {'content-type':'application/json', 'X-Admin-Token': token}, body: JSON.stringify({title, body})});
      if (!res.ok) throw new Error('create failed');
      const j = await res.json();
      alert('Task created: ' + (j.id || j.task_id || ''));
    }catch(e){ alert('Failed creating task'); }
  };
  if (btnDelegateInShowMe) btnDelegateInShowMe.onclick = async () => {
    try{
      const text = document.getElementById('msg') ? document.getElementById('msg').value : '';
      const title = prompt('Task title?'); if (!title) return;
      const r = await fetch('/agent/plan', { method: 'POST', headers: {'content-type':'application/json'}, body: JSON.stringify({ title, body: text || '(no body)' }) });
      if(!r.ok){ alert('Failed to create task'); return; }
      const data = await r.json(); if (data && data.task_id){ alert('Planner created task ' + data.task_id); }
    }catch(e){ alert('Failed to delegate'); }
  };

// auto-mount the coding panel if present (progressive enhancement)
try{
  const mount = document.getElementById('coding-panel-mount');
  if(mount && window.initCodingPanel){ window.initCodingPanel(mount); }
}catch(_){}

  // Sessions stats panel
  async function loadSessionStats(){
    try{
      const r = await fetch('/agent/api/sessions?page=1&page_size=10');
      // route is mounted under /agent in code above; if /api/sessions mounted at /agent/api/sessions adjust:
    }catch{}
  }

  // Settings
  async function loadSettings() {
    try{
      const res = await fetch('/api/public/auto_continue');
      if (res.ok){
        const j = await res.json();
        if (j && j.auto_continue === true) return true;
        return false;
      }
    }catch(e){ /* ignore */ }
    try {
      $('#settingsBox').textContent = '(settings API unavailable — UI will still work; Save disabled)';
      $('#settingsNote').textContent = '';
      const btn = $('#saveSettings'); if (btn) btn.disabled = true;
    } catch(_) {}
    return false;
  }
  $('#saveSettings') && ($('#saveSettings').onclick = async () => {
    try {
      const payload = {
        tts_speed: parseFloat($('#ttsSpeed').value || '1.0'),
        queue_reminder_minutes: parseInt($('#queueMinutes').value || '5', 10),
        agent_use_langgraph: !!$('#agentUseLanggraph').checked,
      };
      setStatus('saving…');
  const token = $('#adminToken') ? $('#adminToken').value.trim() : '';
  const headers = {'content-type':'application/json'};
  if (token) headers['X-Admin-Token'] = token;
  const r = await fetch('/api/settings', {method:'POST', headers: headers, body: JSON.stringify(payload)});
      if (!r.ok) throw new Error(await r.text());
      const body = await r.json();
      await loadSettings();
      setStatus('saved');
      if (body && body.applied_in_process) {
        $('#langgraphNote').textContent = 'applied in-process';
        setSettingsBanner('LangGraph change applied in-process', false);
        if (payload.agent_use_langgraph !== undefined) setLangPill(payload.agent_use_langgraph);
      } else if (payload.agent_use_langgraph !== undefined) {
        $('#langgraphNote').textContent = 'restart may be required';
        setSettingsBanner('LangGraph change saved; server restart required to apply', true);
      }
      setTimeout(()=>setStatus(''),900);
    } catch(e) {
      setStatus('save failed');
      log('[settings error] ' + e);
    }
  });

  // New settings UI helpers (Supabase-backed)
  async function ui_load_settings() {
    const token = $('#adminToken') ? $('#adminToken').value.trim() : '';
    const headers = {};
    if (token) headers['X-Admin-Token'] = token;
    try {
      const r = await fetch('/api/settings', {headers});
      if (!r.ok) throw new Error(await r.text());
      const body = await r.json();
      return body;
    } catch (e) { return {ok:false, error: String(e)}; }
  }

  async function ui_save_settings(map) {
    const token = $('#adminToken') ? $('#adminToken').value.trim() : '';
    const headers = {'content-type':'application/json'};
    if (token) headers['X-Admin-Token'] = token;
    try {
      const r = await fetch('/api/settings', {method:'PUT', headers, body: JSON.stringify(map)});
      const body = await r.json();
      return body;
    } catch(e) { return {ok:false, error: String(e)}; }
  }

  // wire admin token saved earlier to load settings fields in the S pane
  $('#saveadmintoken') && ($('#saveadmintoken').onclick = () => { const t = $('#adminToken').value.trim(); if(t) { localStorage.setItem('X_ADMIN_TOKEN', t); alert('Admin token saved locally.'); } });
  // Rotate admin token via API
  const RAILWAY_VARS_URL = 'https://railway.com/project/451db926-5f6b-4131-9035-f4a9481cad5b/service/3392195a-b847-48a0-bd42-ebfd5138770a/variables?environmentId=6a7439e0-62ec-4331-b6f5-5d0777955795';
  $('#rotateAdminBtn') && ($('#rotateAdminBtn').onclick = async () => {
  if (!window.vmConfirm) window.vmConfirm = async function(m){ try{ const r=await fetch('/api/settings'); const j=await r.json(); const s=j.settings||{}; if(s.auto_continue==='true'||s.auto_continue===true) return true; }catch(e){} return confirm(m); };
  if (!await window.vmConfirm('Rotate admin token? This will generate a new token and save it to settings. Current UI-saved token will no longer work. Continue?')) return;
    const token = $('#adminToken') ? $('#adminToken').value.trim() : '';
    const headers = {'content-type':'application/json'};
    if (token) headers['X-Admin-Token'] = token;
    try {
      const r = await fetch('/api/settings/rotate_admin', {method:'POST', headers});
      const body = await r.json();
      if (!r.ok || !body.ok) { alert('Rotate failed: '+(body.error||JSON.stringify(body))); return; }
      const newtok = body.new_token || '';
      const el = $('#rotatedToken'); if (el) el.textContent = 'New token generated — copy and store securely.';
      // Show new token briefly and offer to copy
      if (newtok) {
        const save = await window.vmConfirm('New admin token generated. Click OK to copy it to clipboard (and optionally save to local storage).');
        if (save) {
          try { await navigator.clipboard.writeText(newtok); alert('New token copied to clipboard — paste/store it in Railway env and GitHub secret.'); } catch(e) { alert('Copy failed — token copied to clipboard.'); }
          const store = await window.vmConfirm('Save the new token to localStorage for this browser? (Not secure for shared machines)');
          if (store) { localStorage.setItem('X_ADMIN_TOKEN', newtok); $('#adminToken').value = newtok; }
        }
        // Open Railway variables page to allow quick paste/update
        if (await window.vmConfirm('Open Railway variables page to update SETTINGS_ADMIN_TOKEN now?')) {
          try { window.open(RAILWAY_VARS_URL, '_blank'); } catch(e) { /* ignore */ }
        }
      }
      await loadSettings();
    } catch(e) { alert('Rotate error: '+e); }
  });
  $('#loadsettings') && ($('#loadsettings').onclick = async ()=>{
    const res = await ui_load_settings();
    if (!res.ok) { alert('load failed: '+(res.error||JSON.stringify(res))); return; }
    const s = res.settings || {};
    ['OPENAI_MODEL','AGENT_TOOLS_ENABLED','OPENAI_API_KEY','SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_ANON_KEY'].forEach(k=>{ const el = $('#s_'+k); if(el) el.value = s[k] ?? ''; });
    setSettingsBanner('Loaded settings (secrets masked). Use Save to rotate keys.');
  });
  $('#savesettings') && ($('#savesettings').onclick = async ()=>{
    const body = {};
    ['OPENAI_MODEL','AGENT_TOOLS_ENABLED','OPENAI_API_KEY','SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_ANON_KEY'].forEach(k=>{ const el = $('#s_'+k); if(el && el.value.trim().length) body[k]=el.value.trim(); });
    if (!Object.keys(body).length) { alert('Nothing to save'); return; }
    const res = await ui_save_settings(body);
    if (!res.ok) { alert('save failed: '+JSON.stringify(res)); return; }
    alert('Saved keys: '+JSON.stringify(res.updated||[]));
  });


  // Sessions list (left panel)
  async function loadSessions() {
    try{
      const r = await fetch('/agent/sessions?limit=20');
      const rows = r.ok ? await r.json() : [];
      const sel = $('#sessionSelect'); if(!sel) return;
      const prev = sel.value;
      sel.innerHTML = '<option value="">(select session)</option>' + rows.map(s => {
        const label = s.label || '';
        const when = (s.created_at || '').split('T')[0] || '';
        return `<option value="${s.id}">${s.id}${label ? ' • '+label : ''}${when ? ' • '+when : ''}</option>`;
      }).join('');
      if (prev) sel.value = prev;
    }catch{}
  }
  $('#sessionSelect') && ($('#sessionSelect').onchange = async (e) => {
    currentSessionId = e.target.value || null;
    pill(currentSessionId);
    await loadRecent(currentSessionId);
  });
  $('#refreshSessions') && ($('#refreshSessions').onclick = loadSessions);

  // Recent messages for a session
  async function loadRecent(sessionId) {
    if (!sessionId) return;
    try {
      const r = await fetch(`/agent/messages?session_id=${encodeURIComponent(sessionId)}&limit=12`);
      if (!r.ok) return;
      const rows = await r.json();
      log(`--- recent ${rows.length} message(s) for session ${sessionId} ---`);
      rows.forEach(row => { log(`[${row.role}] ${row.content}`); });
    } catch {}
  }

  // Supabase mini select runner
  const sbRun = $('#sbRun');
  if (sbRun) sbRun.onclick = async () => {
    const table = $('#sbTable').value.trim();
    const limit = parseInt($('#sbLimit').value || '5', 10);
    if (!table) { $('#sbOut').textContent = '(enter table name)'; return; }
    $('#sbOut').textContent = 'running…';
    try{
      const q = new URLSearchParams({table, limit: String(limit)});
      const r = await fetch(`/agent/select?${q.toString()}`);
      const data = r.ok ? await r.json() : [];
      $('#sbOut').textContent = JSON.stringify(data, null, 2);
    }catch(e){ $('#sbOut').textContent = '[error] ' + e; }
  };

  // Send chat
  const newSessionBtn = $('#newSessionBtn');
  if (newSessionBtn) newSessionBtn.onclick = () => { nextNewSession = true; newSessionBtn.textContent = 'Will start new session on next send'; };
  const sendBtn = $('#send');
  if (sendBtn) sendBtn.onclick = async () => {
    const msg = $('#msg').value.trim();
    const label = $('#label') ? ($('#label').value.trim() || undefined) : undefined;
    if (!msg) return;
    setStatus('sending…');
    try {
      const body = nextNewSession ? {message: msg, label} : {message: msg, label, session_id: currentSessionId || undefined};
      nextNewSession = false; if (newSessionBtn) newSessionBtn.textContent = 'New session on send';
      const r = await fetch('/agent/chat', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(body)});
      const data = await r.json();
      if (r.ok) {
        if (data.session_id) currentSessionId = data.session_id;
        pill(currentSessionId);
        log(`> ${msg}`);
        log(data.text);
        await loadSessions();
        await loadRecent(currentSessionId);
      } else {
        log('[error] ' + JSON.stringify(data));
      }
    } catch(e) {
      log('[error] ' + e);
    } finally {
      setStatus(''); const ta=$('#msg'); if(ta) ta.value='';
    }
  };

  // init
  pill(currentSessionId);
  setModeText('Chat');
  loadSettings();
  loadSessions();

  // Insert a lightweight 'education' seed into the conversation log to help the human operator
  (function insertAgentSeed(){
    try{
      const seed = `SYSTEM SEED: V-Me2 Agent — Role and Environment:\n- You are V-Me2, an assistant embedded in a FastAPI app (V-Me2).\n- Available tools: LangGraph agent (if enabled), /agent/* endpoints for reading files, planning, and ops tasks, and Email UI (drafting).\n- Data sources: a Supabase copy of Gmail (read-only for now) and a Supabase queue table for outgoing messages — integration managed outside this UI.\n- Goal: help the human iterate on connectors, author prompts, and improve automation.\n- Safety: do not attempt to send real emails until the Supabase queue is wired and authorized.\n\nCopy this seed into chat as the first message to educate the agent about its environment.`;
      const el = document.getElementById('log'); if (!el) return;
      const wrapper = document.createElement('div'); wrapper.style.opacity = '0.95'; wrapper.style.background = '#071'; wrapper.style.padding = '8px'; wrapper.style.borderRadius = '8px'; wrapper.style.margin = '8px 0'; wrapper.style.color = '#e9f9ea'; wrapper.style.fontSize = '13px';
      wrapper.innerText = seed;
      const btn = document.createElement('button'); btn.textContent = 'Copy seed to clipboard'; btn.style.marginLeft = '8px'; btn.onclick = async ()=>{ try{ await navigator.clipboard.writeText(seed); alert('Seed copied to clipboard — paste into chat.'); }catch(e){ alert('Copy failed — select and copy manually.'); } };
      wrapper.appendChild(document.createElement('br'));
      wrapper.appendChild(btn);
      el.insertBefore(wrapper, el.firstChild);
    }catch(e){ /* ignore */ }
  })();

  // Defensive: if the coding panel elements aren't present on this page
  // (for example /showme which doesn't inline coding.html), inject an
  // iframe that points at the standalone coding page so the composer
  // exists and is usable. This keeps initialization simple and avoids
  // fragile DOM-insert/script-execution ordering issues.
  (function ensureCodingPanel(){
    try{
      if (!document.querySelector('#coding-main') && location.pathname && location.pathname.indexOf('/showme') === 0) {
        const mount = document.createElement('div');
        mount.id = 'coding-iframe-mount';
        mount.style.margin = '12px 0';
        const ifr = document.createElement('iframe');
        ifr.id = 'coding-iframe';
        ifr.src = '/static/coding.html?v=' + Date.now();
        ifr.title = 'Coding panel (embedded)';
        ifr.style.width = '100%';
        ifr.style.height = '560px';
        ifr.style.border = '1px solid #232530';
        ifr.style.borderRadius = '10px';
        mount.appendChild(ifr);
        // insert after the main wrap so styles stay consistent
        const wrap = document.querySelector('.wrap') || document.body;
        wrap.parentNode.insertBefore(mount, wrap.nextSibling);
        ifr.addEventListener('load', ()=>{ try{ console.info('Embedded coding panel loaded'); }catch(e){} });
      }
    }catch(e){ console.warn('ensureCodingPanel failed', e); }
  })();
})();
