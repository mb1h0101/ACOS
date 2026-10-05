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
    if(m.type==='thumb' && agents[m.agent_id]){
      agents[m.agent_id]._thumb=m.data;
      paintThumb(m.agent_id);
    }
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
    const old=agents[a.agent_id];
    a._thumb=old&&old._thumb;
    agents[a.agent_id]=a;
    let el=$('#a-'+a.agent_id);
    if(!el){
      el=document.createElement('div');
      el.id='a-'+a.agent_id;
      el.className='tile';
      el.innerHTML='<div class="thumb"></div><div class="name"></div><div class="meta"></div>';
      grid.appendChild(el);
    }
    el.className='tile'+(!a.online?' offline':'')+(a.protected_from_classroom?' teacher':'');
    el.querySelector('.name').textContent=a.protected_from_classroom?'教師機（受保護）':'學生 '+a.agent_id.slice(-4);
    const state=!a.online?'離線':a.overlay==='FOCUS_NOW'?'正在看老師':a.mode==='FREE'?'未套用課堂限制':'課堂中';
    el.querySelector('.meta').innerHTML=`<span class="dot ${a.online?'on':''}"></span>${state}`;
    paintThumb(a.agent_id);
  });
  document.querySelectorAll('.tile').forEach(el=>{
    const id=el.id.slice(2);
    if(!seen.has(id)) el.remove();
  });
}

function paintThumb(id){
  const el=$('#a-'+id);
  if(!el) return;
  const th=el.querySelector('.thumb');
  if(agents[id]&&agents[id]._thumb) th.style.backgroundImage=`url(data:image/jpeg;base64,${agents[id]._thumb})`;
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
  $('#site_allow').value=(p.site_allow||[]).join('\n');
  $('#app_allow').value=(p.app_allow||[]).join('\n');
  $('#teachertest').checked=!!s.allow_teacher_test;
}

$('#apply').onclick=async()=>{
  const sites=lines($('#site_allow').value), apps=lines($('#app_allow').value);
  $('#apply').disabled=true;
  $('#applymsg').textContent='套用中…';
  try{
    await command({action:'set_policy',mode:'EXERCISE',patch:{
      site_mode:sites.length?'allowlist':'off',site_allow:sites,site_block:[],
      app_mode:apps.length?'allowlist':'off',app_allow:apps,app_block:[],
      fullscreen:false,kill_blocked_apps:false
    },targets:'all'});
    await command({action:'set_mode',mode:'EXERCISE',targets:'all'});
    await command({action:'set_overlay',overlay:'NONE',targets:'all'});
    $('#applymsg').textContent='已套用。學生可在上述範圍內操作，其他未允許資源會被阻擋。';
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

$('#thumbs').onclick=()=>command({action:'request_thumbs',targets:'all'});

$('#teachertest').onchange=async()=>{
  await command({action:'set_teacher_test',enabled:$('#teachertest').checked,targets:'all'});
};

loadSetup();
connect();