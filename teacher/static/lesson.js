const $=s=>document.querySelector(s);
let lesson=null;
let completed=new Set();
async function load(){
  lesson=await (await fetch('/api/lesson')).json();
  $('#title').textContent=lesson.title||'ACOS Lesson';
  $('#rule').textContent=`Complete all tasks. First-attempt accuracy ≥ ${lesson.min_accuracy}% earns ${lesson.reward_seconds}s Reward.`;
  const host=$('#questions'); host.innerHTML='';
  if(!lesson.enabled){ $('#summary').textContent='This lesson is not enabled.'; return; }
  lesson.questions.forEach((q,i)=>{
    const d=document.createElement('div'); d.className='lesson-q';
    d.innerHTML=`<b>${i+1}. ${escapeHtml(q.prompt)}</b><input autocomplete="off" data-id="${q.id}" placeholder="Type your answer"><button class="act primary" style="margin-top:8px">Submit</button><div class="lesson-result"></div>`;
    const input=d.querySelector('input'), btn=d.querySelector('button'), res=d.querySelector('.lesson-result');
    btn.onclick=()=>submit(q.id,input,res,btn);
    input.onkeydown=e=>{if(e.key==='Enter') btn.click();};
    host.appendChild(d);
  });
  updateSummary();
}
async function submit(task_id,input,res,btn){
  if(!input.value.trim()) return;
  btn.disabled=true;
  try{
    const r=await fetch('/api/lesson/answer',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({task_id,answer:input.value})});
    const j=await r.json();
    if(!j.ok){ res.className='lesson-result bad'; res.textContent=j.error||'Cannot submit'; btn.disabled=false; return; }
    if(j.correct){
      completed.add(task_id); res.className='lesson-result good'; res.textContent=`Correct ✓ (${j.completed}/${j.total})`; input.disabled=true; btn.disabled=true;
    }else{
      res.className='lesson-result bad'; res.textContent=`Not yet — try again (attempt ${j.attempt})`; btn.disabled=false; input.focus();
    }
    if(j.qualified_for_reward) $('#summary').textContent=`Completed — Reward unlocked for ${lesson.reward_seconds}s.`;
    else updateSummary(j);
  }catch(e){ res.className='lesson-result bad'; res.textContent='Connection error'; btn.disabled=false; }
}
function updateSummary(j){
  const done=j?.completed??completed.size, total=j?.total??lesson?.questions?.length??0;
  const acc=j?.first_attempt_accuracy;
  $('#summary').textContent=`Completed ${done}/${total}`+(acc!=null?` · First-attempt accuracy ${acc}%`:'');
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));}
load();
