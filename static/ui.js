// (2025-09-23 18:28 ET) — Minimal chat UI wiring for /agent/chat
(function(){
	const root = document.currentScript && document.currentScript.parentElement ? document.currentScript.parentElement : document.body;
	const box = document.createElement('div');
	box.innerHTML = `
		<style>
			.vm-wrap{max-width:820px;margin:1rem auto;font-family:system-ui}
			textarea{width:100%;min-height:90px}
			.row{display:flex;gap:.5rem;margin-top:.5rem}
			.log{white-space:pre-wrap;background:#fafafa;border:1px solid #eee;padding:.75rem;margin-top:1rem;min-height:3rem}
			button{padding:.5rem 1rem}
			input{padding:.4rem .6rem;width:220px}
		</style>
		<div class="vm-wrap">
			<div class="row">
				<input id="label" placeholder="session label (optional)"/>
			</div>
			<textarea id="msg" placeholder="Type a message (e.g., /ls .)"></textarea>
			<div class="row">
				<button id="send">Send</button>
				<span id="status"></span>
			</div>
			<div class="log" id="log"></div>
		</div>`;
	root.appendChild(box);
	const $ = (id)=>box.querySelector(id);
	$('#send').onclick = async () => {
		const message = $('#msg').value.trim();
		const label = $('#label').value.trim() || undefined;
		if(!message){return}
		$('#status').textContent = '…sending';
		try{
			const res = await fetch('/agent/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({message,label})});
			const data = await res.json();
			$('#log').textContent += `\n> ${message}\n${data.text}\n(session: ${data.session_id})\n`;
			$('#msg').value = '';
		}catch(e){
			$('#log').textContent += `\n[error] ${e}`;
		}finally{
			$('#status').textContent = '';
		}
	}
})();

// Settings helpers (PUT + POST /refresh)
async function getSettings(adminToken){
	const r = await fetch('/api/settings', { headers:{'X-Admin-Token': adminToken}});
	if(!r.ok) throw new Error('settings get failed');
	return await r.json();
}

async function putSettings(adminToken, patch){
	const r = await fetch('/api/settings',{method:'PUT',headers:{'content-type':'application/json','X-Admin-Token':adminToken},body:JSON.stringify(patch)});
	if(!r.ok) throw new Error(await r.text());
}

async function refreshSettings(adminToken){
	const r = await fetch('/api/settings/refresh',{method:'POST', headers:{'X-Admin-Token':adminToken}});
	if(!r.ok) throw new Error(await r.text());
}

async function saveAndRefresh(adminToken, patch){
	await putSettings(adminToken, patch);
	await refreshSettings(adminToken);
	// optional toast
	try{ if(window.toast) toast('Settings saved & refreshed ✓') }catch(e){}
}
