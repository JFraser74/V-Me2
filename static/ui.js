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

// --- Minimal settings panel helpers ---
async function showSettingsPanel(adminToken){
	try{
		const data = await getSettings(adminToken);
		const settings = data.settings || data;
		let panel = document.getElementById('vme-settings-panel');
		if(!panel){
			panel = document.createElement('div');
			panel.id = 'vme-settings-panel';
			panel.style.marginTop = '1rem';
			document.currentScript.parentElement.appendChild(panel);
		}
		panel.innerHTML = `
			<h3>Settings</h3>
			<div>CI admin token (masked): <input id="ci_token" value="${settings.CI_SETTINGS_ADMIN_TOKEN||''}" placeholder="paste token to save" style="width:420px"/></div>
			<div style="margin-top:.5rem"><button id="save_ci">Save CI token</button> <button id="rotate_admin">Rotate UI admin token</button> <span id="settings_status"></span></div>
			<div style="font-size:90%;color:#666;margin-top:.5rem">Notes: Saving CI token writes to Supabase va_settings (masked). To change later, overwrite this value or use repo secrets for GitHub Actions as needed.</div>
		`;
		document.getElementById('save_ci').onclick = async ()=>{
			const v = document.getElementById('ci_token').value.trim();
			try{ document.getElementById('settings_status').textContent='…saving'; await saveAndRefresh(adminToken, {'CI_SETTINGS_ADMIN_TOKEN': v}); document.getElementById('settings_status').textContent='saved'; }catch(e){ document.getElementById('settings_status').textContent='error'; }
		};
		document.getElementById('rotate_admin').onclick = async ()=>{
			try{
				document.getElementById('settings_status').textContent='rotating…';
				const r = await fetch('/api/settings/rotate_admin',{method:'POST', headers:{'X-Admin-Token': adminToken}});
				const j = await r.json();
				if(j && j.new_token){
					// Show the new token to the user to copy
					prompt('New admin token (copy this and store it somewhere secure):', j.new_token);
					document.getElementById('settings_status').textContent='rotated';
				} else {
					document.getElementById('settings_status').textContent='rotate failed';
				}
			}catch(e){ document.getElementById('settings_status').textContent='error'; }
		};
	}catch(e){ console.error('showSettingsPanel',e); }
}

// Expose to window so operators can call showSettingsPanel(adminToken) from console
window.showSettingsPanel = showSettingsPanel;

// Inject a small Goals iframe into the minimal /ui page if present
(function(){
	try{
		const root = document.currentScript && document.currentScript.parentElement ? document.currentScript.parentElement : document.body;
		const el = document.createElement('div');
		el.style.marginTop = '1rem';
		el.innerHTML = `<h3>Goals</h3><iframe src="/static/goals.html" style="width:100%;height:260px;border:1px solid #ddd;border-radius:6px"></iframe>`;
		root.appendChild(el);
	}catch(e){/* ignore */}
})();
