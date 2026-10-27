const $=s=>document.querySelector(s);
let agents={};
let selected=new Set();
let scope='all';
let focusActive=false;

async function command(body){
  const r=await fetch('/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok) throw new Error('command failed');
  return r.json();
}

function onlineStudents(){
  return Object.values(agents).filter(a=>a.online && !a.protected_from_classroom);
}
function targets(){
  if(scope==='all') return 'all';
  return [...selected].filter(id=>agents[id]&&agents[id].online&&!agents[id].protected_from_classroom);
}
function targetLabel(){
  if(scope==='all') return '全班';
  return `已選 ${targets().length} 位學生`;
}
function updateTargetUI(){
  $('#scope_all').classList.toggle('active',scope==='all');
  $('#scope_selected').classList.toggle('active',scope==='selected');
  $('#selected_count').textContent=selected.size;
  $('#apply').textContent=`套用到${targetLabel()}`;
  $('#focus').textContent=focusActive?'讓學生繼續操作':`請${targetLabel()}看老師`;
  $('#controlhint').textContent=`目前控制對象：${targetLabel()}。`;
  document.querySelectorAll('.tile').forEach(el=>{
    const id=el.dataset.id;
    el.classList.toggle('selected',selected.has(id));
  });
}

function connect(){
  const ws=new WebSocket(`ws://${location.host}/ws/console`);
  ws.onopen=()=>{ $('#conn').textContent='已連線'; $('#conn').className='pill ok'; };
  ws.onclose=()=>{ $('#conn').textContent='重新連線中…'; $('#conn').className='pill bad'; setTimeout(connect,1500); };
  ws.onmessage=e=>{ const m=JSON.parse(e.data); if(m.type==='state') renderState(m); };
}

function renderState(m){
  $('#online').textContent=m.online;
  $('#total').textContent=m.total;
  if(typeof m.allow_teacher_test==='boolean') $('#teachertest').checked=m.allow_teacher_test;

  agents={};
  const grid=$('#grid');
  grid.innerHTML='';
  (m.agents||[]).sort((a,b)=>(a.device_name||a.agent_id).localeCompare(b.device_name||b.agent_id)).forEach(a=>{
    agents[a.agent_id]=a;
    const el=document.createElement('button');
    el.type='button';
    el.dataset.id=a.agent_id;
    el.className='tile'+(!a.online?' offline':'')+(a.protected_from_classroom?' teacher':'');
    const device=a.protected_from_classroom?'教師機（受保護）':(a.device_name||('學生 '+a.agent_id.slice(-4)));
    const state=!a.online?'離線':
      a.overlay_ok===false?'「請看老師」未顯示':
      a.overlay==='FOCUS_NOW'?'已顯示「請看老師」':
      a.mode==='FREE'?'未套用課堂限制':'已套用課堂限制';
    el.innerHTML=`<div class="pick">${selected.has(a.agent_id)?'✓':''}</div><div class="name">${device}</div><div class="meta"><span class="dot ${a.online?'on':''}"></span>${state}</div>`;
    if(!a.protected_from_classroom && a.online){
      el.onclick=()=>{
        if(selected.has(a.agent_id)) selected.delete(a.agent_id); else selected.add(a.agent_id);
        scope='selected';
        updateTargetUI();
      };
    }else{
      el.disabled=true;
    }
    grid.appendChild(el);
  });
  for(const id of [...selected]) if(!agents[id]) selected.delete(id);

  const active=scope==='all'?onlineStudents():targets().map(id=>agents[id]).filter(Boolean);
  focusActive=active.length>0 && active.every(a=>a.overlay==='FOCUS_NOW');
  updateTargetUI();
}

function updateEffect(){
  const sm=$('#site_mode').value, am=$('#app_mode').value;
  const text=[];
  text.push(sm==='off'?'網站：不限制':sm==='allowlist'?'網站：只有符合關鍵字的頁面可用':'網站：符合關鍵字的頁面會被攔');
  text.push(am==='off'?'App：不限制':am==='allowlist'?'App：只有清單內可用':'App：清單內會被攔');
  $('#effect').textContent=text.join('　｜　');
}
const lines=v=>v.split('\n').map(x=>x.trim()).filter(Boolean);

async function loadSetup(){
  const s=await (await fetch('/api/state')).json();
  const p=(s.policies&&s.policies.EXERCISE)||{};
  $('#site_mode').value=p.site_mode||'off';
  $('#site_list').value=(p.site_mode==='blocklist'?(p.site_block||[]):(p.site_allow||[])).join('\n');
  $('#app_mode').value=p.app_mode||'off';
  $('#app_list').value=(p.app_mode==='blocklist'?(p.app_block||[]):(p.app_allow||[])).join('\n');
  $('#teachertest').checked=!!s.allow_teacher_test;
  updateEffect();
}
$('#site_mode').onchange=updateEffect;
$('#app_mode').onchange=updateEffect;

$('#scope_all').onclick=()=>{scope='all';updateTargetUI();};
$('#scope_selected').onclick=()=>{scope='selected';updateTargetUI();};
$('#select_all').onclick=()=>{selected=new Set(onlineStudents().map(a=>a.agent_id));scope='selected';updateTargetUI();};
$('#clear_selection').onclick=()=>{selected.clear();scope='selected';updateTargetUI();};

$('#release_selected').onclick=async()=>{
  if(selected.size===0){ $('#applymsg').textContent='請先選學生。'; return; }
  const t=targets();
  await command({action:'restore_all',targets:t});
  $('#applymsg').textContent=`已解除 ${t.length} 位學生的限制。`;
};

$('#apply').onclick=async()=>{
  const t=targets();
  if(scope==='selected' && t.length===0){ $('#applymsg').textContent='請先選學生。'; return; }
  const siteMode=$('#site_mode').value, appMode=$('#app_mode').value;
  const sites=lines($('#site_list').value), apps=lines($('#app_list').value);
  $('#apply').disabled=true; $('#applymsg').textContent='套用中…';
  try{
    await command({action:'set_policy',mode:'EXERCISE',patch:{
      site_mode:siteMode,
      site_allow:siteMode==='allowlist'?sites:[],
      site_block:siteMode==='blocklist'?sites:[],
      app_mode:appMode,
      app_allow:appMode==='allowlist'?apps:[],
      app_block:appMode==='blocklist'?apps:[],
      fullscreen:false,kill_blocked_apps:false
    },targets:t});
    await command({action:'set_mode',mode:'EXERCISE',targets:t});
    await command({action:'set_overlay',overlay:'NONE',targets:t});
    $('#applymsg').textContent=`已套用到${targetLabel()}。`;
  }catch(e){ $('#applymsg').textContent='套用失敗，請確認學生端是否在線。'; }
  finally{$('#apply').disabled=false;}
};

$('#focus').onclick=async()=>{
  const t=targets();
  if(scope==='selected' && t.length===0){ $('#applymsg').textContent='請先選學生。'; return; }
  $('#focus').disabled=true;
  try{
    await command({action:'set_overlay',overlay:focusActive?'NONE':'FOCUS_NOW',targets:t});
    focusActive=!focusActive; updateTargetUI();
  }finally{$('#focus').disabled=false;}
};

$('#restore').onclick=async()=>{
  if(!confirm('要結束課堂並解除全班學生電腦的 ACOS 限制嗎？')) return;
  await command({action:'restore_all',targets:'all'});
  $('#applymsg').textContent='課堂已結束，全班已恢復一般操作。';
};

$('#teachertest').onchange=async()=>{
  await command({action:'set_teacher_test',enabled:$('#teachertest').checked,targets:'all'});
};

loadSetup(); connect(); updateTargetUI();