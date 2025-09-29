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
      Email: 'PLACEHOLDER — Gmail-like UI, queue drafts/attachments.',
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
  }
  document.querySelectorAll('#modes .tab').forEach(btn=>{
    btn.onclick = () => {
      document.querySelectorAll('#modes .tab').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      setModeText(btn.dataset.mode);
    };
  });

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
    try {
      const r = await fetch('/api/settings');
      if (!r.ok) throw new Error('not ok');
      const data = await r.json();
      $('#settingsBox').textContent = JSON.stringify(data, null, 2);
      if (typeof data.tts_speed === 'number') $('#ttsSpeed').value = data.tts_speed;
      if (typeof data.queue_reminder_minutes === 'number') $('#queueMinutes').value = data.queue_reminder_minutes;
  if (typeof data.agent_use_langgraph === 'boolean') { $('#agentUseLanggraph').checked = data.agent_use_langgraph; setLangPill(data.agent_use_langgraph); }
      $('#settingsNote').textContent = 'Loaded from /api/settings';
    } catch {
      $('#settingsBox').textContent = '(settings API unavailable — UI will still work; Save disabled)';
      $('#settingsNote').textContent = '';
      const btn = $('#saveSettings'); if (btn) btn.disabled = true;
    }
  }
  // Goals panel (load and render compact table)
  async function loadGoals() {
    try {
      const r = await fetch('/status/goals');
      if (!r.ok) throw new Error('failed');
      const d = await r.json();
      const items = (d.items || []).slice(0, 50);
      const box = document.getElementById('goalsBox');
      if (!box) return;
      if (!items.length) { box.textContent = '(no goals found)'; return; }
      const tbl = document.createElement('table');
      tbl.style.width = '100%'; tbl.style.borderCollapse = 'collapse'; tbl.style.fontSize = '13px';
      const thead = document.createElement('thead'); thead.innerHTML = '<tr><th style="text-align:left;padding:6px">Goal</th><th style="text-align:left;padding:6px">Status</th></tr>';
      const tbody = document.createElement('tbody');
      items.forEach(it => {
        const tr = document.createElement('tr');
        const g = document.createElement('td'); g.style.padding='6px'; g.textContent = it.goal || '';
        const s = document.createElement('td'); s.style.padding='6px';
        const st = String(it.status||'');
        const span = document.createElement('span'); span.textContent = st; span.style.padding='4px 8px'; span.style.borderRadius='6px'; span.style.fontSize='12px';
        if (st.toUpperCase().startsWith('DONE')) { span.style.background='#ecfdf5'; span.style.color='#065f46'; }
        else if (st.toUpperCase().startsWith('WAITING')) { span.style.background='#fff7ed'; span.style.color='#9a3412'; }
        else { span.style.background='#eef2ff'; span.style.color='#3730a3'; }
        s.appendChild(span);
        tr.appendChild(g); tr.appendChild(s); tbody.appendChild(tr);
      });
      tbl.appendChild(thead); tbl.appendChild(tbody);
      box.innerHTML = ''; box.appendChild(tbl);
    } catch (e) {
      const box = document.getElementById('goalsBox'); if (box) box.textContent = '(failed to load goals)';
    }
  }
  // load goals once on init
  loadGoals();
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
    if (!confirm('Rotate admin token? This will generate a new token and save it to settings. Current UI-saved token will no longer work. Continue?')) return;
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
        const save = confirm('New admin token generated. Click OK to copy it to clipboard (and optionally save to local storage).');
        if (save) {
          try { await navigator.clipboard.writeText(newtok); alert('New token copied to clipboard — paste/store it in Railway env and GitHub secret.'); } catch(e) { alert('Copy failed — token: '+newtok); }
          const store = confirm('Save the new token to localStorage for this browser? (Not secure for shared machines)');
          if (store) { localStorage.setItem('X_ADMIN_TOKEN', newtok); $('#adminToken').value = newtok; }
        }
        // Open Railway variables page to allow quick paste/update
        if (confirm('Open Railway variables page to update SETTINGS_ADMIN_TOKEN now?')) {
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

  // Auto-load values into new settings inputs on page load
  (async function autoLoadSettingsInputs(){
    try{
      const res = await ui_load_settings();
      if (!res || !res.ok) return;
      const s = res.settings || {};
      const keys = ['OPENAI_API_KEY','OPENAI_MODEL','AGENT_TOOLS_ENABLED','SUPABASE_URL','SUPABASE_ANON_KEY','SUPABASE_SERVICE_ROLE_KEY'];
      keys.forEach(k=>{ const el = document.getElementById('s_'+k); if(el) el.value = s[k] ?? ''; });
    }catch(e){ /* ignore */ }
  })();

  // Header settings dropdown wiring
  const headerBtn = document.getElementById('headerSettingsBtn');
  const headerDropdown = document.getElementById('headerSettingsDropdown');
  if (headerBtn && headerDropdown) {
    headerBtn.onclick = async () => {
      headerDropdown.style.display = headerDropdown.style.display === 'none' ? 'block' : 'none';
      // lazy-load values from Supabase-backed settings into header fields
      try {
        const res = await ui_load_settings();
        if (res && res.ok) {
          const s = res.settings || {};
          document.getElementById('h_OPENAI_API_KEY').value = s.OPENAI_API_KEY || '';
          document.getElementById('h_SUPABASE_URL').value = s.SUPABASE_URL || '';
          document.getElementById('h_SUPABASE_SERVICE_ROLE_KEY').value = s.SUPABASE_SERVICE_ROLE_KEY || '';
        }
      } catch(e) { /* ignore */ }
    };
    document.getElementById('headerCloseSettings').onclick = () => { headerDropdown.style.display = 'none'; };
    document.getElementById('headerSaveSettings').onclick = async () => {
      const map = {};
      ['OPENAI_API_KEY','SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY'].forEach(k => {
        const el = document.getElementById('h_'+k);
        if (el && el.value && el.value.trim().length) map[k] = el.value.trim();
      });
      if (!Object.keys(map).length) { alert('Nothing to save'); return; }
      try {
        const res = await ui_save_settings(map);
        if (!res.ok) { alert('save failed: '+JSON.stringify(res)); return; }
        alert('Saved: '+JSON.stringify(res.updated||[]));
        headerDropdown.style.display = 'none';
      } catch(e){ alert('save error: '+e); }
    };
  }

  // Mode settings placeholder wiring
  const modeSettingsBtn = document.getElementById('modeSettingsBtn');
  if (modeSettingsBtn) {
    modeSettingsBtn.onclick = () => {
      alert('Mode settings panel placeholder — will be implemented per-mode.');
    };
  }

  // Wire mic buttons: voice opens mic.html, meeting toggles meeting overlay and API calls
  const micToggle = document.getElementById('micToggle');
  const meetingToggle = document.getElementById('meetingToggle');
  const meetingOverlay = document.getElementById('meetingOverlay');
  const meetingIdEl = document.getElementById('meetingId');
  const meetingTranscript = document.getElementById('meetingTranscript');
  const ingestBtn = document.getElementById('ingestSegmentBtn');
  const endMeetingBtn = document.getElementById('endMeetingBtn');
  let currentMeetingId = null;

  if (micToggle) micToggle.onclick = () => { window.open('/static/mic.html', '_blank'); };

  if (meetingToggle) meetingToggle.onclick = async () => {
    // Toggle overlay
    if (meetingOverlay.style.display === 'none' || meetingOverlay.style.display === '') {
      // begin meeting via API
      try {
        const r = await fetch('/api/meeting/begin', {method:'POST'});
        const j = await r.json();
        currentMeetingId = j.meeting_id || null;
        meetingIdEl.textContent = currentMeetingId || '(none)';
        meetingTranscript.value = '';
        meetingOverlay.style.display = 'flex';
      } catch(e){ alert('Failed to start meeting: '+e); }
    } else {
      // hide overlay
      meetingOverlay.style.display = 'none';
    }
  };

  if (ingestBtn) ingestBtn.onclick = async () => {
    if (!currentMeetingId) { alert('No meeting started'); return; }
    const text = meetingTranscript.value.trim();
    if (!text) { alert('Enter a transcript segment first'); return; }
    try {
      const r = await fetch('/api/meeting/ingest', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({meeting_id: currentMeetingId, text})});
      const j = await r.json();
      if (j.ok) { alert('Segment ingested'); meetingTranscript.value = ''; }
      else alert('Ingest failed');
    } catch(e){ alert('Ingest error: '+e); }
  };

  if (endMeetingBtn) endMeetingBtn.onclick = async () => {
    if (!currentMeetingId) { meetingOverlay.style.display = 'none'; return; }
    try {
      const r = await fetch('/api/meeting/end', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({meeting_id: currentMeetingId})});
      const j = await r.json();
      if (j && j.summary) { alert('Meeting ended — summary:\n'+j.summary); }
      currentMeetingId = null;
      meetingOverlay.style.display = 'none';
    } catch(e){ alert('End meeting error: '+e); }
  };

  // Hook Save button to persist both non-secret settings and secret keys via PUT
  $('#saveSettings') && ($('#saveSettings').onclick = async () => {
    try{
      const payload = {};
      // non-secret UI settings persisted via POST /api/settings (existing flow)
      payload.tts_speed = parseFloat($('#ttsSpeed').value || '1.0');
      payload.queue_reminder_minutes = parseInt($('#queueMinutes').value || '5', 10);
      payload.agent_use_langgraph = !!$('#agentUseLanggraph').checked;
      const token = $('#adminToken') ? $('#adminToken').value.trim() : '';
      const headers = {'content-type':'application/json'}; if (token) headers['X-Admin-Token']=token;
      // First POST the simple settings (apply in-process where possible)
      const r1 = await fetch('/api/settings', {method:'POST', headers, body: JSON.stringify(payload)});
      if (!r1.ok) throw new Error('Failed saving basic settings');
      const body1 = await r1.json();
      // Now collect secret keys from the new fields and PUT them via /api/settings (Supabase-backed)
      const putMap = {};
      ['OPENAI_API_KEY','OPENAI_MODEL','AGENT_TOOLS_ENABLED','SUPABASE_URL','SUPABASE_ANON_KEY','SUPABASE_SERVICE_ROLE_KEY'].forEach(k=>{
        const el = document.getElementById('s_'+k);
        if (el && el.value && el.value.trim().length) putMap[k] = el.value.trim();
      });
      if (Object.keys(putMap).length) {
        const r2 = await fetch('/api/settings', {method:'PUT', headers, body: JSON.stringify(putMap)});
        if (!r2.ok) throw new Error('Failed saving secret settings');
        await r2.json();
        // Trigger refresh so runtime picks up changes if possible
        await fetch('/api/settings/refresh', {method:'POST', headers});
      }
      // reload settings display
      await loadSettings();
      setStatus('saved');
    }catch(e){ setStatus('save failed'); log('[settings error] '+e); }
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
})();
