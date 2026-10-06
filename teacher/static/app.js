const $=s=>document.querySelector(s);
let agents={};
let focusActive=false;

async function command(body){
  const r=await fetch('/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok) throw new Error('command failed');
  return r.json();
}

function connect(){
  const ws=new WebSocket(`ws://${location.host}/ws/console`);
  ws.onopen=()=>{ $('#conn').textContent='已連線'; $('#conn').className='pill ok'; };
  ws.onclose=()=>{ $('#conn').textContent='重新連線中…'; $('#conn').className='pill bad'; setTimeout(connect,1500); };
  ws.onmessage=e=>{
    const m=JSON.parse(e.data);
    if(m.type==='state') renderState(m);
  };
}

function renderState(m){
  $('#online').textContent=m.online;
  $('#total').textContent=m.total;
  if(typeof m.allow_teacher_test==='boolean') $('#teachertest').checked=m.allow_teacher_test;

  const activeStudents=(m.agents||[]).filter(a=>a.online && !a.protected_from_classroom);
  focusActive=activeStudents.length>0 && activeStudents.every(a=>a.overlay==='FOCUS_NOW');
  renderFocus();

  const grid=$('#grid'), seen=new Set();
  (m.agents||[]).sort((a,b)=>a.agent_id.localeCompare(b.agent_id)).forEach(a=>{
    seen.add(a.agent_id);
    agents[a.agent_id]=a;
    let el=$('#a-'+a.agent_id);
    if(!el){
      el=document.createElement('div');
      el.id='a-'+a.agent_id;
      el.className='tile';
      el.innerHTML='<div class="name"></div><div class="meta"></div>';
      grid.appendChild(el);
    }
    el.className='tile'+(!a.online?' offline':'')+(a.protected_from_classroom?' teacher':'');
    const device=a.device_name||('學生 '+a.agent_id.slice(-4));
    el.querySelector('.name').textContent=a.protected_from_classroom?'教師機（受保護）':device;
    const state=!a.online?'離線':
      a.overlay_ok===false?'「請看老師」未顯示':
      a.overlay==='FOCUS_NOW'?'已顯示「請看老師」':
      a.mode==='FREE'?'未套用課堂限制':'課堂中';
    el.querySelector('.meta').innerHTML=`<span class="dot ${a.online?'on':''}"></span>${state}`;
  });
  document.querySelectorAll('.tile').forEach(el=>{
    const id=el.id.slice(2);
    if(!seen.has(id)) el.remove();
  });
}

function renderFocus(){
  const b=$('#focus');
  if(focusActive){
    b.textContent='讓學生繼續操作';
    b.classList.add('active');
    $('#controlhint').textContent='全班目前暫停操作、看老師。學生原本工作仍保留。';
  }else{
    b.textContent='請全班看老師';
    b.classList.remove('active');
    $('#controlhint').textContent='學生目前可以在你設定的範圍內操作。';
  }
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
}

$('#apply').onclick=async()=>{
  const siteMode=$('#site_mode').value;
  const appMode=$('#app_mode').value;
  const sites=lines($('#site_list').value), apps=lines($('#app_list').value);
  $('#apply').disabled=true;
  $('#applymsg').textContent='套用中…';
  try{
    await command({action:'set_policy',mode:'EXERCISE',patch:{
      site_mode:siteMode,
      site_allow:siteMode==='allowlist'?sites:[],
      site_block:siteMode==='blocklist'?sites:[],
      app_mode:appMode,
      app_allow:appMode==='allowlist'?apps:[],
      app_block:appMode==='blocklist'?apps:[],
      fullscreen:false,kill_blocked_apps:false
    },targets:'all'});
    await command({action:'set_mode',mode:'EXERCISE',targets:'all'});
    await command({action:'set_overlay',overlay:'NONE',targets:'all'});
    $('#applymsg').textContent='已套用到全班。';
  }catch(e){
    $('#applymsg').textContent='套用失敗，請確認學生端是否在線。';
  }finally{
    $('#apply').disabled=false;
  }
};

$('#focus').onclick=async()=>{
  $('#focus').disabled=true;
  try{
    await command({action:'set_overlay',overlay:focusActive?'NONE':'FOCUS_NOW',targets:'all'});
    focusActive=!focusActive;
    renderFocus();
  }finally{
    $('#focus').disabled=false;
  }
};

$('#restore').onclick=async()=>{
  if(!confirm('要結束課堂並解除所有學生電腦的 ACOS 限制嗎？')) return;
  await command({action:'restore_all',targets:'all'});
  $('#applymsg').textContent='課堂已結束，學生電腦已恢復一般操作。';
};

$('#teachertest').onchange=async()=>{
  await command({action:'set_teacher_test',enabled:$('#teachertest').checked,targets:'all'});
};

loadSetup();
connect();