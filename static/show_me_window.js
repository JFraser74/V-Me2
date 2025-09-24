(function(){
  const $ = (sel) => document.querySelector(sel);
  let nextNewSession = false;
  let currentSessionId = null;

  const setStatus = (t) => { $('#status') && ($('#status').textContent = t || ''); };
  const log = (t) => { const el=$('#log'); if(!el) return; el.textContent += (t + "\n"); el.scrollTop = el.scrollHeight; };
  const pill = (id) => { const el=$('#session-pill'); if(el) el.textContent = 'session: ' + (id || 'n/a'); };

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
      $('#settingsNote').textContent = 'Loaded from /api/settings';
    } catch {
      $('#settingsBox').textContent = '(settings API unavailable — UI will still work; Save disabled)';
      $('#settingsNote').textContent = '';
      const btn = $('#saveSettings'); if (btn) btn.disabled = true;
    }
  }
  $('#saveSettings') && ($('#saveSettings').onclick = async () => {
    try {
      const payload = {
        tts_speed: parseFloat($('#ttsSpeed').value || '1.0'),
        queue_reminder_minutes: parseInt($('#queueMinutes').value || '5', 10),
      };
      setStatus('saving…');
      const r = await fetch('/api/settings', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(payload)});
      if (!r.ok) throw new Error(await r.text());
      await loadSettings();
      setStatus('saved');
      setTimeout(()=>setStatus(''),900);
    } catch(e) {
      setStatus('save failed');
      log('[settings error] ' + e);
    }
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
