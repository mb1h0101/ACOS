// ACOS Teacher Console UI. No external dependencies (school networks may block CDNs).
const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
let selected = null;          // agent_id or null => whole class
let agents = {};              // agent_id -> public state
let broadcasting = false;

function targets(){ return (selected && !$('#selall').checked) ? [selected] : "all"; }

async function cmd(body){
  body.targets = body.targets || targets();
  const r = await fetch('/api/command',{method:'POST',
    headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  return r.json();
}

// ---- live connection to console ------------------------------------------
function connect(){
  const ws = new WebSocket(`ws://${location.host}/ws/console`);
  ws.onopen = ()=>{ $('#conn').textContent='live'; $('#conn').className='pill ok'; };
  ws.onclose = ()=>{ $('#conn').textContent='reconnecting…'; $('#conn').className='pill bad';
    setTimeout(connect,1500); };
  ws.onmessage = e=>{
    const m = JSON.parse(e.data);
    if(m.type==='state') renderState(m);
    else if(m.type==='thumb'){ if(agents[m.agent_id]){ agents[m.agent_id]._thumb=m.data; paintThumb(m.agent_id);} }
    else if(m.type==='milestone') flash(`Class reached ${m.pct}% completion`);
  };
}

function renderState(m){
  $('#online').textContent=m.online; $('#total').textContent=m.total;
  $('#classmode').textContent=m.class_mode;
  $$('.mode').forEach(b=>b.classList.toggle('active',b.dataset.mode===m.class_mode));
  if(m.reward_remaining>0){ $('#rewardpill').classList.remove('hidden');
    $('#rewardleft').textContent=m.reward_remaining; }
  else $('#rewardpill').classList.add('hidden');
  const grid=$('#grid'); const seen=new Set();
  m.agents.sort((a,b)=>(a.label||a.agent_id).localeCompare(b.label||b.agent_id));
  m.agents.forEach(a=>{
    seen.add(a.agent_id);
    const prev=agents[a.agent_id]; a._thumb=prev&&prev._thumb; agents[a.agent_id]=a;
    let t=$('#t-'+a.agent_id);
    if(!t){ t=document.createElement('div'); t.className='tile'; t.id='t-'+a.agent_id;
      t.onclick=()=>selectAgent(a.agent_id);
      t.innerHTML=`<span class="badge ovl hidden"></span>
        <div class="thumb"></div>
        <div class="meta"><span class="label"></span><span class="st"></span></div>`;
      grid.appendChild(t); }
    t.classList.toggle('offline',!a.online);
    t.classList.toggle('sel', selected===a.agent_id && !$('#selall').checked);
    t.querySelector('.label').textContent = a.label || seatName(a);
    t.querySelector('.st').innerHTML =
      `<span class="dot ${a.online?'on':'off'}"></span><span class="badge ${a.mode}">${a.mode}</span>`;
    const ovl=t.querySelector('.ovl');
    if(a.overlay && a.overlay!=='NONE'){ ovl.classList.remove('hidden'); ovl.textContent=a.overlay; }
    else ovl.classList.add('hidden');
    paintThumb(a.agent_id);
  });
  // remove tiles for agents no longer present
  $$('.tile').forEach(t=>{ const id=t.id.slice(2); if(!seen.has(id)) t.remove(); });
}
function seatName(a){ return 'Seat '+a.agent_id.slice(-4); }
function paintThumb(id){ const t=$('#t-'+id); if(!t)return;
  const th=t.querySelector('.thumb');
  if(agents[id]&&agents[id]._thumb) th.style.backgroundImage=`url(data:image/jpeg;base64,${agents[id]._thumb})`;
}

function selectAgent(id){
  if($('#selall').checked){ $('#selall').checked=false; }
  selected = (selected===id)? null : id;
  if(!selected) $('#selall').checked=true;
  updateSel();
}
function updateSel(){
  const all=$('#selall').checked;
  $('#selinfo').textContent = all ? 'Targeting: all students. Click a tile to target one.'
    : 'Targeting: '+((agents[selected]&&(agents[selected].label||seatName(agents[selected])))||selected);
  $$('.tile').forEach(t=>t.classList.toggle('sel',!all&&t.id==='t-'+selected));
}
$('#selall').onchange=()=>{ if($('#selall').checked) selected=null; updateSel(); };

function flash(msg){ const p=$('#conn'); const old=p.textContent; p.textContent=msg;
  setTimeout(()=>p.textContent=old,2500); }

// ---- mode / overlay buttons ----------------------------------------------
$$('.mode').forEach(b=>b.onclick=()=>{
  const mode=b.dataset.mode;
  const body={action:'set_mode',mode};
  if(mode==='REWARD') body.reward_seconds=parseInt($('#rewardsec').value||'0',10);
  cmd(body);
});
$('#focusnow').onclick=()=>cmd({action:'set_overlay',overlay:'FOCUS_NOW'});
$('#blackout').onclick=()=>cmd({action:'set_overlay',overlay:'BLACKOUT'});
$('#clearoverlay').onclick=()=>cmd({action:'set_overlay',overlay:'NONE'});
$('#emergency').onclick=()=>{ if(confirm('Emergency: return ALL students to EXERCISE and clear overlays?')) cmd({action:'emergency_focus',targets:'all'}); };
$('#thumbs').onclick=()=>cmd({action:'request_thumbs'});
$('#bcast').onclick=()=>{
  broadcasting=!broadcasting;
  $('#bcast').classList.toggle('on',broadcasting);
  $('#bcast').textContent = broadcasting?'7 · Stop broadcast':'7 · Broadcast my screen';
  cmd({action: broadcasting?'broadcast_start':'broadcast_stop', fps:1.0});
};

// ---- policy editor --------------------------------------------------------
let policies={};
async function loadPolicies(){ const s=await (await fetch('/api/state')).json();
  policies=s.policies; fillPolicy(); }
function fillPolicy(){
  const p=policies[$('#polmode').value]||{};
  $('#site_mode').value=p.site_mode||'off';
  $('#site_allow').value=(p.site_allow||[]).join('\n');
  $('#site_block').value=(p.site_block||[]).join('\n');
  $('#app_mode').value=p.app_mode||'off';
  $('#app_allow').value=(p.app_allow||[]).join('\n');
  $('#app_block').value=(p.app_block||[]).join('\n');
  $('#kill_blocked_apps').checked=!!p.kill_blocked_apps;
  $('#fullscreen').checked=!!p.fullscreen;
}
$('#polmode').onchange=fillPolicy;
const lines=v=>v.split('\n').map(x=>x.trim()).filter(Boolean);
$('#savepol').onclick=async()=>{
  const mode=$('#polmode').value;
  const patch={ site_mode:$('#site_mode').value, site_allow:lines($('#site_allow').value),
    site_block:lines($('#site_block').value), app_mode:$('#app_mode').value,
    app_allow:lines($('#app_allow').value), app_block:lines($('#app_block').value),
    kill_blocked_apps:$('#kill_blocked_apps').checked, fullscreen:$('#fullscreen').checked };
  await cmd({action:'set_policy',mode,patch,targets:'all'});
  policies[mode]=Object.assign({},policies[mode],patch);
  flash('Policy saved for '+mode);
};

// ---- tabs + analytics -----------------------------------------------------
$$('.tab').forEach(t=>t.onclick=()=>{
  $$('.tab').forEach(x=>x.classList.remove('active')); t.classList.add('active');
  $$('.tabpane').forEach(p=>p.classList.add('hidden'));
  $('#tab-'+t.dataset.tab).classList.remove('hidden');
  if(t.dataset.tab==='analytics') loadAnalytics();
});
async function loadAnalytics(){
  const d=await (await fetch('/api/analytics')).json();
  $('#kpi_completion').textContent=(d.completion.pct||0)+'%';
  $('#kpi_accuracy').textContent=(d.first_attempt_accuracy.pct||0)+'%';
  const p50=x=>x&&x.p50!=null?x.p50+'ms':'–';
  $('#kpi_cmd').textContent=p50(d.latency.agent_command_latency);
  $('#kpi_thumb').textContent=p50(d.latency.thumbnail_latency);
  $('#kpi_bcast').textContent=p50(d.latency.broadcast_latency);
  $('#kpi_mode').textContent=p50(d.latency.mode_transition_latency);
  const tb=$('#counts'); tb.innerHTML='';
  Object.entries(d.counts).sort().forEach(([k,v])=>{
    tb.insertAdjacentHTML('beforeend',`<tr><td>${k}</td><td>${v}</td></tr>`);});
}
setInterval(()=>{ if(!$('#tab-analytics').classList.contains('hidden')) loadAnalytics(); },4000);

// keyboard shortcuts 1-6
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='TEXTAREA'||e.target.tagName==='INPUT'||e.target.tagName==='SELECT')return;
  const map={'1':'DEMO','2':'EXERCISE','3':'REWARD','4':'FREE'};
  if(map[e.key]) $$('.mode').find(b=>b.dataset.mode===map[e.key]).click();
  if(e.key==='5') $('#focusnow').click();
  if(e.key==='6') $('#blackout').click();
});


// ---- lesson / task builder -----------------------------------------------
function parseLessonLines(text){
  const out=[];
  text.split(/\r?\n/).forEach((line,i)=>{
    const parts=line.split('::');
    if(parts.length<2) return;
    const prompt=parts.shift().trim();
    const answer=parts.join('::').trim();
    if(prompt && answer) out.push({id:`q${i+1}`,prompt,answer});
  });
  return out;
}
async function loadLesson(){
  try{
    const s=await (await fetch('/api/state')).json();
    const l=s.lesson||{};
    $('#lesson_enabled').checked=!!l.enabled;
    $('#lesson_title').value=l.title||'';
    $('#lesson_accuracy').value=l.min_accuracy??80;
    $('#lesson_reward').value=l.reward_seconds??300;
    $('#lesson_questions').value=(l.questions||[]).map(q=>`${q.prompt} :: ${q.answer||''}`).join('\n');
    $('#lesson_url').textContent=s.lesson_url||'—';
  }catch(e){}
}
$('#saveLesson').onclick=async()=>{
  const questions=parseLessonLines($('#lesson_questions').value);
  if(!questions.length){ flash('Add at least one Question :: Answer line'); return; }
  const body={
    enabled:$('#lesson_enabled').checked,
    title:$('#lesson_title').value.trim()||"Today's lesson",
    questions,
    min_accuracy:parseInt($('#lesson_accuracy').value||'80',10),
    reward_seconds:parseInt($('#lesson_reward').value||'300',10),
  };
  const r=await fetch('/api/lesson',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();
  if(j.ok){
    $('#lessonSaved').textContent=`Saved ${questions.length} tasks. Reward: all completed + first-attempt accuracy ≥ ${body.min_accuracy}% → ${body.reward_seconds}s.`;
    $('#lesson_url').textContent=j.lesson_url||$('#lesson_url').textContent;
    flash('Lesson saved');
  }else flash('Lesson save failed');
};

connect(); loadPolicies(); loadLesson();
