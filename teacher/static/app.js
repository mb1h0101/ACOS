const $=s=>document.querySelector(s);
let agents={}, selected=new Set(), scope='all', intent='free', focusActive=false;

async function command(body){
  const r=await fetch('/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok) throw new Error('command failed');
  return r.json();
}
const lines=v=>v.split('\n').map(x=>x.trim()).filter(Boolean);
function onlineStudents(){ return Object.values(agents).filter(a=>a.online&&!a.protected_from_classroom); }
function targets(){ return scope==='all'?'all':[...selected].filter(id=>agents[id]?.online&&!agents[id]?.protected_from_classroom); }
function targetLabel(){ return scope==='all'?'全班':`已選 ${targets().length} 位學生`; }

function renderIntent(){
  document.querySelectorAll('.intent').forEach(b=>b.classList.toggle('active',b.dataset.intent===intent));
  $('#resourcePanel').classList.toggle('hidden',intent==='free');
  const action=intent==='free'?'網站與 App 自主操作':intent==='allow'?'只使用指定學習資源':'暫時避開指定資源';
  $('#summary').textContent=`${targetLabel()}：${action}。`;
  $('#apply').textContent=`套用到${targetLabel()}`;
  $('#controlhint').textContent=`目前控制對象：${targetLabel()}。`;
  if(!focusActive) $('#focus').textContent=`請${targetLabel()}看老師`;
}
function renderTargets(){
  $('#scope_all').classList.toggle('active',scope==='all');
  $('#scope_selected').classList.toggle('active',scope==='selected');
  $('#selected_count').textContent=selected.size;
  document.querySelectorAll('.tile').forEach(el=>el.classList.toggle('selected',selected.has(el.dataset.id)));
  renderIntent();
}

function connect(){
  const ws=new WebSocket(`ws://${location.host}/ws/console`);
  ws.onopen=()=>{ $('#conn').textContent='已連線'; $('#conn').className='pill ok'; };
  ws.onclose=()=>{ $('#conn').textContent='重新連線中…'; $('#conn').className='pill bad'; setTimeout(connect,1500); };
  ws.onmessage=e=>{ const m=JSON.parse(e.data); if(m.type==='state') renderState(m); };
}
function renderState(m){
  $('#online').textContent=m.online; $('#total').textContent=m.total;
  if(typeof m.allow_teacher_test==='boolean') $('#teachertest').checked=m.allow_teacher_test;
  agents={}; const grid=$('#grid'); grid.innerHTML='';
  (m.agents||[]).sort((a,b)=>(a.device_name||a.agent_id).localeCompare(b.device_name||b.agent_id)).forEach(a=>{
    agents[a.agent_id]=a;
    const el=document.createElement('button'); el.type='button'; el.dataset.id=a.agent_id;
    el.className='tile'+(!a.online?' offline':'')+(a.protected_from_classroom?' teacher':'');
    const name=a.protected_from_classroom?'教師機（受保護）':(a.device_name||('學生 '+a.agent_id.slice(-4)));
    const state=!a.online?'離線':a.overlay_ok===false?'注意畫面未顯示':a.overlay==='FOCUS_NOW'?'正在看老師':a.mode==='FREE'?'自主操作':'課堂規則已套用';
    el.innerHTML=`<div class="pick">${selected.has(a.agent_id)?'✓':''}</div><div class="name">${name}</div><div class="meta"><span class="dot ${a.online?'on':''}"></span>${state}</div>`;
    if(!a.protected_from_classroom&&a.online){
      el.onclick=()=>{ selected.has(a.agent_id)?selected.delete(a.agent_id):selected.add(a.agent_id); scope='selected'; renderTargets(); };
    } else el.disabled=true;
    grid.appendChild(el);
  });
  for(const id of [...selected]) if(!agents[id]) selected.delete(id);
  const active=scope==='all'?onlineStudents():targets().map(id=>agents[id]).filter(Boolean);
  focusActive=active.length>0&&active.every(a=>a.overlay==='FOCUS_NOW');
  $('#focus').classList.toggle('active',focusActive);
  if(focusActive) $('#focus').textContent='讓學生繼續操作';
  renderTargets();
}
async function loadSetup(){
  const s=await (await fetch('/api/state')).json();
  $('#teachertest').checked=!!s.allow_teacher_test;
}

document.querySelectorAll('.intent').forEach(b=>b.onclick=()=>{ intent=b.dataset.intent; renderIntent(); });
$('#scope_all').onclick=()=>{ scope='all'; renderTargets(); };
$('#scope_selected').onclick=()=>{ scope='selected'; renderTargets(); };
$('#select_all').onclick=()=>{ selected=new Set(onlineStudents().map(a=>a.agent_id)); scope='selected'; renderTargets(); };
$('#clear_selection').onclick=()=>{ selected.clear(); scope='selected'; renderTargets(); };

$('#release_selected').onclick=async()=>{
  const t=[...selected].filter(id=>agents[id]?.online&&!agents[id]?.protected_from_classroom);
  if(!t.length){ $('#applymsg').textContent='請先點選要解除的學生。'; return; }
  await command({action:'restore_all',targets:t});
  $('#applymsg').textContent=`已解除 ${t.length} 位學生限制。`;
};

$('#apply').onclick=async()=>{
  const t=targets();
  if(scope==='selected'&&!t.length){ $('#applymsg').textContent='請先點選學生。'; return; }
  const sites=lines($('#site_list').value), apps=lines($('#app_list').value);
  let siteMode='off', appMode='off';
  if(intent==='allow'){ siteMode=sites.length?'allowlist':'off'; appMode=apps.length?'allowlist':'off'; }
  if(intent==='block'){ siteMode=sites.length?'blocklist':'off'; appMode=apps.length?'blocklist':'off'; }
  $('#apply').disabled=true; $('#applymsg').textContent='套用中…';
  try{
    await command({action:'set_policy',mode:'EXERCISE',patch:{
      site_mode:siteMode,site_allow:siteMode==='allowlist'?sites:[],site_block:siteMode==='blocklist'?sites:[],
      app_mode:appMode,app_allow:appMode==='allowlist'?apps:[],app_block:appMode==='blocklist'?apps:[],
      fullscreen:false,kill_blocked_apps:false
    },targets:t});
    await command({action:'set_mode',mode:intent==='free'?'FREE':'EXERCISE',targets:t});
    await command({action:'set_overlay',overlay:'NONE',targets:t});
    $('#applymsg').textContent=`已套用：${targetLabel()}。`;
  }catch(e){ $('#applymsg').textContent='套用失敗，請確認學生端是否在線。'; }
  finally{ $('#apply').disabled=false; }
};

$('#focus').onclick=async()=>{
  const t=targets();
  if(scope==='selected'&&!t.length){ $('#applymsg').textContent='請先點選學生。'; return; }
  $('#focus').disabled=true;
  try{
    await command({action:'set_overlay',overlay:focusActive?'NONE':'FOCUS_NOW',targets:t});
    focusActive=!focusActive;
    $('#focus').classList.toggle('active',focusActive);
    $('#focus').textContent=focusActive?'讓學生繼續操作':`請${targetLabel()}看老師`;
  } finally { $('#focus').disabled=false; }
};
$('#restore').onclick=async()=>{
  if(!confirm('要結束課堂並解除全班 ACOS 限制嗎？')) return;
  await command({action:'restore_all',targets:'all'});
  intent='free'; renderIntent();
  $('#applymsg').textContent='全班已恢復一般操作。';
};
$('#teachertest').onchange=async()=>command({action:'set_teacher_test',enabled:$('#teachertest').checked,targets:'all'});

loadSetup(); connect(); renderIntent();