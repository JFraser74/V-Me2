(function(){
  // Very small coding panel: left tree (ls), right editor (read/write), bottom git status/diff/commit.
  function el(tag, attrs={}, children=[]){
    const e=document.createElement(tag);
    Object.entries(attrs).forEach(([k,v])=>{
      if(k==='class') e.className=v; else if(k==='text') e.textContent=v; else e.setAttribute(k,v);
    });
    (Array.isArray(children)?children:[children]).filter(Boolean).forEach(c=>e.appendChild(c));
    return e;
  }
  async function jget(u){const r=await fetch(u); if(!r.ok) throw new Error(await r.text()); return r.json()}
  async function jpost(u, body, headers){
    const r=await fetch(u,{method:'POST',headers:Object.assign({'content-type':'application/json'},headers||{}),body:JSON.stringify(body||{})});
    let t; try{t=await r.json()}catch{t={raw:await r.text()}}
    if(!r.ok) throw new Error(typeof t==='string'?t:JSON.stringify(t));
    return t;
  }
  async function ls(path){
    const res = await jget('/fs/ls?path='+encodeURIComponent(path||'.')); return res.result||'';
  }
  async function read(path, start=0, end=200000){
    const res = await jpost('/fs/read',{path,start,end}); return res.result||'';
  }
  async function write({path, content, confirm, create_dirs, adminToken}){
    const headers = adminToken? {'X-Admin-Token':adminToken} : {};
    const res = await jpost('/fs/write',{path,content,confirm,create_dirs}, headers); return res.result||'';
  }
  async function gitStatus(){ const res=await jget('/fs/git/status'); return res.result||''; }
  async function gitDiff(){ const res=await jget('/fs/git/diff'); return res.result||''; }
  async function gitCommit({message, add_all, confirm, adminToken}){
    const headers = adminToken? {'X-Admin-Token':adminToken} : {};
    const res=await jpost('/fs/git/commit',{message,add_all,confirm}, headers); return res.result||'';
  }
  function render(container){
    container.innerHTML='';
    container.appendChild(el('style', {text: `
      .cp-wrap{display:grid;grid-template-columns:280px 1fr;grid-template-rows:auto 1fr auto;gap:.75rem;height:70vh;font-family:system-ui}
      .cp-top{grid-column:1/3;display:flex;gap:.5rem}
      .cp-tree{border:1px solid #eee;padding:.5rem;overflow:auto;background:#fafafa}
      .cp-editor{display:flex;flex-direction:column}
      .cp-editor textarea{flex:1;min-height:200px}
      .cp-bottom{grid-column:1/3;display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
      .cp-box{border:1px solid #eee;padding:.5rem;background:#fff;white-space:pre-wrap;overflow:auto;min-height:120px}
      .cp-row{display:flex;gap:.5rem;align-items:center}
    `}));
    const wrap = el('div',{class:'cp-wrap'});
    const top = el('div',{class:'cp-top'});
    const pathIn = el('input',{placeholder:'path (e.g. . , static , routes )', value:'.'});
    const listBtn = el('button',{text:'List'});
    const loadBtn = el('button',{text:'Open'});
    const fileIn = el('input',{placeholder:'file to open (e.g. routes/agent.py)'});
    const adminIn = el('input',{placeholder:'X-Admin-Token (for writes/commit)'});
    top.append(pathIn,listBtn,fileIn,loadBtn,adminIn);

    const tree = el('div',{class:'cp-tree', text:'(ls results...)'});
    const editor = el('div',{class:'cp-editor'});
    const ta = el('textarea',{placeholder:'file content…'});
    const edRow = el('div',{class:'cp-row'});
    const saveDry = el('button',{text:'Save (dry-run)'}); 
    const saveReal = el('button',{text:'Save (confirm)'}); 
    const saveStatus = el('span',{text:''});
    edRow.append(saveDry, saveReal, saveStatus);
    editor.append(ta, edRow);

    const bottom = el('div',{class:'cp-bottom'});
    const boxStatus = el('div',{class:'cp-box', text:'(git status)…'});
    const boxDiff = el('div',{class:'cp-box', text:'(git diff)…'});
    const commitRow = el('div',{class:'cp-row'});
    const msgIn = el('input',{placeholder:'commit message'});
    const commitDry = el('button',{text:'Commit (dry-run)'}); 
    const commitReal = el('button',{text:'Commit (confirm)'}); 
    commitRow.append(msgIn,commitDry,commitReal);
    bottom.append(boxStatus, boxDiff, commitRow);

    wrap.append(top, tree, editor, bottom);
    container.appendChild(wrap);

    listBtn.onclick = async ()=>{
      try{ tree.textContent = (await ls(pathIn.value||'.')) || '(empty)'; }
      catch(e){ tree.textContent = '[error] '+e; }
    };
    loadBtn.onclick = async ()=>{
      try{ ta.value = await read(fileIn.value||''); }
      catch(e){ ta.value = ''; alert(e); }
    };
    saveDry.onclick = async ()=>{
      saveStatus.textContent='…saving (dry-run)';
      try{ saveStatus.textContent = await write({path:fileIn.value||'', content:ta.value, confirm:false, create_dirs:true, adminToken:adminIn.value}); }
      catch(e){ saveStatus.textContent='[error] '+e; }
    };
    saveReal.onclick = async ()=>{
      saveStatus.textContent='…saving (confirm)';
      try{ saveStatus.textContent = await write({path:fileIn.value||'', content:ta.value, confirm:true, create_dirs:true, adminToken:adminIn.value}); }
      catch(e){ saveStatus.textContent='[error] '+e; }
    };
    const refreshGit = async ()=>{
      try{ boxStatus.textContent = await gitStatus(); }catch(e){ boxStatus.textContent='[error] '+e; }
      try{ boxDiff.textContent   = await gitDiff(); }catch(e){ boxDiff.textContent='[error] '+e; }
    };
    commitDry.onclick = async ()=>{
      try{ alert(await gitCommit({message:msgIn.value||'(no message)', add_all:true, confirm:false, adminToken:adminIn.value})); await refreshGit(); }
      catch(e){ alert(e); }
    };
    commitReal.onclick = async ()=>{
      try{ alert(await gitCommit({message:msgIn.value||'(no message)', add_all:true, confirm:true, adminToken:adminIn.value})); await refreshGit(); }
      catch(e){ alert(e); }
    };
    // Auto-load
    listBtn.click(); refreshGit();
  }
  // Surface a hook the Show Me window can call.
  window.initCodingPanel = render;
})();