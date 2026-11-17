/* Shared helpers for every page: storage, the data file, the Climb (ladder) state, the Plug & Play
   calendar, and the workout log. Everything is saved on the phone (localStorage) under vault:*. */
const EMBED_OK=!/claude|anthropic/i.test(location.hostname) && location.protocol!=='file:';
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const store={
  get(k,d){try{const v=localStorage.getItem(k);return v?JSON.parse(v):d}catch(e){return d}},
  set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}},
  del(k){try{localStorage.removeItem(k)}catch(e){}}
};
const DAY=864e5;
const ymd=d=>{d=d instanceof Date?d:new Date(d);const z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${z(d.getMonth()+1)}-${z(d.getDate())}`};
const TODAY=ymd(new Date());
const parseYmd=s=>{const [y,m,d]=s.split('-').map(Number);return new Date(y,m-1,d)};
const monday=d=>{d=new Date(d);d.setHours(0,0,0,0);d.setDate(d.getDate()-((d.getDay()+6)%7));return d};
const WEEKDAYS=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

let _data=null;
async function load(){
  if(_data) return _data;
  const r=await fetch('data/vault.json'); if(!r.ok) throw new Error('did not load');
  _data=await r.json();
  _data.phases.forEach(p=>p.workouts.forEach(w=>{w.phase=p.id;w.days.forEach(d=>{d.workout=w.id;d.phase=p.id})}));
  return _data;
}
const phaseById=(d,id)=>d.phases.find(p=>p.id===id);
const workoutById=(d,id)=>{for(const p of d.phases){const w=p.workouts.find(w=>w.id===id);if(w)return w}return null};
function dayById(d,id){
  for(const p of d.phases)for(const w of p.workouts){const x=w.days.find(x=>x.id===id);if(x)return {phase:p,workout:w,day:x}}
  return null;
}
const stepName=(d,step)=>step===5?d.reset.name:(d.phases.find(p=>p.step===step)||{}).name;

/* ---- the Climb: which step of the ladder, which week, which workout of the phase ---- */
function climb(){return store.get('vault:climb',null)}
function setClimb(c){store.set('vault:climb',c)}
function startClimb(opts){
  const c={cal:opts.cal||'o35',place:opts.place||'gym',step:opts.step||1,cycle:1,stepStart:TODAY,picks:{flf:1,tt:1,ml:1,mb:1},started:TODAY};
  setClimb(c);return c;
}
// Week inside the current step, 1-based. Week 5+ means it is time to climb.
function stepWeek(c){if(!c)return 1;return Math.floor((monday(new Date()).getTime()-monday(parseYmd(c.stepStart)).getTime())/(7*DAY))+1}
function climbUp(d){
  const c=climb(); if(!c) return null;
  if(c.step>=5){ // back to step 1, next workout of each phase
    c.step=1;c.cycle=(c.cycle||1)+1;
    for(const p of d.phases){const n=p.workouts.filter(w=>!w.home).length;c.picks[p.id]=((c.picks[p.id]||1)%n)+1}
  } else c.step++;
  c.stepStart=TODAY;setClimb(c);return c;
}
// The workout (3 days) the Climb points at right now. Step 5 (Reset) uses a Foundation workout, light.
function currentWorkout(d,c){
  c=c||climb(); if(!c) return null;
  const p=d.phases.find(p=>p.step===(c.step===5?1:c.step));
  const base=p.workouts.filter(w=>!w.home);
  const n=((c.picks[p.id]||1)-1)%base.length;
  return placed(d,base[n],c.place);
}
// Gym or home version of a workout. Home PDFs exist for most workouts; the rest fall back to the gym one.
function placed(d,w,place){
  if(place==='home'&&w.homeId){const h=workoutById(d,w.homeId);if(h)return h}
  return w;
}
function dayPlaced(d,dayId,place){
  const x=dayById(d,dayId); if(!x) return null;
  const w=placed(d,workoutById(d,x.workout.base),place);
  const day=w.days.find(y=>y.day===x.day.day)||x.day;
  return {phase:x.phase,workout:w,day};
}

/* ---- the Plug & Play calendar ----
   u35: 3 toning days plus 2 cardio days, same every week.
   o35: 5 training days. Month 1 and Month 2 patterns from the PDFs; odd steps use month 1, even steps month 2. */
const CARDIO=[['Run 30 minutes','Elliptical 30 minutes'],['Jump rope 20 minutes','Cardio machine 30 minutes'],['Cardio machine 30 minutes','Elliptical 30 minutes'],['Run 30 minutes','Elliptical 30 minutes']];
const O35=[ // [Mon..Fri] per week; numbers = Toning Day, 'X' = extra workout, 'F' = Foundation full body, 'R' = reset full body; '+' = add a spice, '=' = repeat
  [[1,2,3,'X','2='],[3,1,2,'X','1+'],[2,3,1,'X','3='],['X',1,2,3,'1+']],
  [[1,2,3,'F','1='],[2,1,3,'X','2+'],[3,2,1,'R','3='],['X',1,2,3,'1+']],
];
function plan(c,week,wd){ // wd 0=Mon..6=Sun, week 1-based inside the step
  const w=((week-1)%4+4)%4;
  if(wd>=5) return {type:'rest',label:wd===5&&c.cal==='u35'?'Off, or an extra workout':'Rest',note:c.cal==='u35'?'Real rest, or an extra workout if you have it in you.':'Light movement, mobility, or full rest. The work between the work is where you tone.'};
  if(c.cal==='u35'){
    if(wd===0) return {type:'toning',day:1,label:'Day 1'};
    if(wd===2) return {type:'toning',day:2,label:'Day 2'};
    if(wd===4) return {type:'toning',day:3,label:'Day 3'};
    return {type:'cardio',label:'Cardio',note:CARDIO[w][wd===1?0:1]+'. Run, jump rope, elliptical or a machine. Mix it up, keep it consistent.'};
  }
  const m=O35[((c.step||1)+1)%2][w][wd];
  if(m==='X') return {type:'extra',label:'Extra',note:'Your 4th workout of the week. Repeat Day 1, 2 or 3 (whichever body part you want more of), or do a Foundation full-body day. This is a day a spice is allowed.'};
  if(m==='F') return {type:'extra',label:'Full body',note:'A full-body day from Fat Loss Foundation. Light weight, high reps.',full:true};
  if(m==='R') return {type:'extra',label:'Reset',note:'A Reset full-body day: a Foundation workout, 2 sets, light.',full:true};
  const day=parseInt(m);
  return {type:'toning',day,label:`Day ${day}`,spice:String(m).includes('+'),repeat:String(m).includes('='),
    note:String(m).includes('+')?'Same workout, with one spice from the Spice Rack.':String(m).includes('=')?'Again, same workout as earlier this week.':''};
}

/* ---- log of finished workouts ---- */
function log(){return store.get('vault:log',[])}
function logDone(day,w,p){const l=log();l.push({t:Date.now(),d:TODAY,id:day.id,name:`${w.name} · Day ${day.day}`,phase:p.id});store.set('vault:log',l.slice(-400))}
function doneOn(date){return log().filter(x=>x.d===date)}
function doneInWeek(mon){const a=ymd(mon),b=ymd(new Date(mon.getTime()+6*DAY));return log().filter(x=>x.d>=a&&x.d<=b)}
const lastWeight=v=>{const a=store.get('vault:wt:'+v,[]);return a.length?a[a.length-1]:null};
function saveWeight(v,w){const a=store.get('vault:wt:'+v,[]);if(a.length&&a[a.length-1].d===TODAY)a[a.length-1].w=w;else a.push({d:TODAY,w});store.set('vault:wt:'+v,a.slice(-20))}

/* ---- exercise display: name/video with home version, swaps, and the explanation of what's special ---- */
function shownEx(d,dayId,e,place){
  const sw=store.get(`vault:swap:${dayId}:${e.code}`,null);
  if(sw) return {...e,name:sw.name,video:sw.video||null,photo:sw.photo||null,startPhoto:null,endPhoto:null,swapped:true,orig:e.name,row:sw.row||e.row};
  if(place==='home'&&e.homeName) return {...e,name:e.homeName,video:e.homeVideo||e.video,photo:e.homeVideo?photoFor(e.homeVideo):e.photo,startPhoto:e.homeVideo?null:e.startPhoto,endPhoto:e.homeVideo?null:e.endPhoto,gymName:e.name,note:e.homeNote||e.note,row:e.homeRow||e.row};
  return e;
}
function photoFor(v){return v?`images/${v}-pdf.webp`:null}
const TEMPO_WORDS=t=>{const m=/^(\d)(\d)(\d)(?:-(\d)(\d)(\d))?$/.exec(t||'');if(!m)return '';
  const one=(a,b,c)=>`${a} down · ${b} hold · ${c} up`;return m[4]?`${one(m[1],m[2],m[3])}, pulses ${one(m[4],m[5],m[6])}`:one(m[1],m[2],m[3])};
function special(e){ // the "spice" baked into this exercise, in one line
  const n=(e.note||'').toLowerCase(), r=e.reps||'';
  const nums=r.split('-').filter(x=>/^\d+$/.test(x));
  if(n.includes('pyramid')||(nums.length>2&&nums.every(x=>x===nums[0]))) return `Pyramid set: ${nums.length>2?nums.length+' sets of '+nums[0]:'10 reps at a time'}. Go up in weight each time, then back down. No rest between.`;
  if(nums.length>2) return `Drop set: ${r} reps. Lighter weight each time, no rest between.`;
  if(/21/.test(n)||r==='7-7-7') return "21's: 7 reps bottom half, 7 reps top half, 7 full reps. No rest between.";
  if(/1\s*½|1 1\/2/.test(n)) return '1½ reps: all the way down, halfway up, back down, all the way up. That is one rep.';
  if(/hold/.test(n)){const m=n.match(/(\d+)s?/);return `Isometric hold: on the last rep, hold the hardest point for ${m?m[1]:20} seconds.`}
  if(/pulse/i.test(e.name)) return 'Pulses: small quick reps in the hardest part of the move. Keep the tension on.';
  if(/per side/.test(r)) return 'Reps are per side.';
  if(/sec/.test(r)) return 'Timed: hold for the seconds shown.';
  return '';
}
function holdSeconds(e){const m=(e.note||'').match(/hold\D*(\d+)/i);if(m)return +m[1];const t=(e.reps||'').match(/^(\d+)(?:-(\d+))?\s*sec/i);return t?+(t[2]||t[1]):0}
function setsLabel(e){const nums=(e.reps||'').split('-').filter(x=>/^\d+$/.test(x));if(!e.sets)return nums.length>2?'1 set':'';return `${e.sets} set${e.sets>1?'s':''}`}

if('serviceWorker' in navigator&&location.protocol==='https:')navigator.serviceWorker.register('sw.js').catch(()=>{});

/* ---- swap sheet: the Vault Coach, built in. Same movement pattern, same muscles, keep the reps, sets, tempo and rest. ---- */
function libraryIndex(d){ // every distinct exercise in the Vault, by swap row
  if(d._lib) return d._lib;
  const seen=new Map();
  for(const p of d.phases)for(const w of p.workouts)for(const day of w.days)for(const b of day.blocks)for(const e of b.exercises){
    const add=(name,video,row,photo)=>{if(!row||!video)return;const k=video;if(!seen.has(k))seen.set(k,{name:name.replace(/ Pulses$/i,''),video,row,photo:photo||photoFor(video)})};
    add(e.name,e.video,e.row,e.photo);
    if(e.homeName&&e.homeVideo) add(e.homeName,e.homeVideo,e.homeRow,null);
  }
  return d._lib=[...seen.values()];
}
function openSwap(d,dayId,e,place,onDone){
  const rows=d.swaps, row=rows[e.row]||null, group=row?row.group:'';
  const lib=libraryIndex(d);
  const same=row?lib.filter(x=>x.video!==e.video&&rows[x.row]&&rows[x.row].group===group&&x.name.toLowerCase()!==e.name.toLowerCase()):[];
  const vault=same.slice(0,12);
  const texts=row?[...row.variations.map(v=>({name:v,why:'Approved variation'})),{name:row.home,why:'At home, no machine'},{name:row.gym,why:'At the gym'}].filter(t=>t.name&&t.name.toLowerCase()!==e.name.toLowerCase()):[];
  const bg=document.createElement('div');bg.className='sheet-bg';
  bg.innerHTML=`<div class="sheet" role="dialog" aria-label="Swap ${esc(e.name)}">
    <button class="x" data-x>Close</button>
    <span class="eyebrow">Swap ${esc(e.code)} · ${esc(e.name)}</span>
    <h2>Same muscles, same plan</h2>
    <p class="note">${row?`<b>${esc(row.muscles)}</b> · ${esc(group)}. `:''}Keep the reps, sets, tempo and rest exactly as written. Only the movement changes.</p>
    ${e.swapped?`<button class="opt text" data-undo><b>Back to ${esc(e.orig)}</b><small>Undo the swap</small></button>`:''}
    ${vault.length?`<h3>From the Vault, with a video</h3>`:''}
    ${vault.map((x,i)=>`<button class="opt" data-pick="${i}"><img src="${esc(x.photo||'')}" alt="" loading="lazy"><span><b>${esc(x.name)}</b><small>${esc(rows[x.row]?rows[x.row].muscles:'')}</small></span></button>`).join('')}
    ${texts.length?`<h3>Other ways to do it</h3><p class="note">No video for these. You know the move or can look it up. Pick one and it goes on your workout.</p>`:''}
    ${texts.map((t,i)=>`<button class="opt text" data-text="${i}"><b>${esc(t.name)}</b><small>${esc(t.why)}</small></button>`).join('')}
    ${!row?`<p class="note">No swap list for this one yet. Pick any exercise that works the same muscles, and keep the reps, sets and rest.</p>`:''}
    <p class="note">Balance check: don't end up with three squat-type moves in one circuit.</p>
  </div>`;
  const close=()=>bg.remove();
  bg.addEventListener('click',ev=>{
    const b=ev.target.closest('button');
    if(ev.target===bg||(b&&b.hasAttribute('data-x'))){close();return}
    if(!b)return;
    const key=`vault:swap:${dayId}:${e.code}`;
    if(b.hasAttribute('data-undo')){store.del(key);close();onDone();return}
    if(b.dataset.pick!==undefined){const x=vault[+b.dataset.pick];store.set(key,{name:x.name,video:x.video,photo:x.photo,row:x.row});close();onDone();return}
    if(b.dataset.text!==undefined){const t=texts[+b.dataset.text];store.set(key,{name:t.name,video:null,photo:null,row:e.row});close();onDone();return}
  });
  document.body.appendChild(bg);
}

/* ---- Michelle's explainer videos (unlisted on YouTube) ---- */
const VIDS={
  orientation:['Orientation: start here','4X48tdVsPpM'],
  blueprint:['The Vault Blueprint: the five phases','SsEOp-p5APQ'],
  ladder:['The Toning Ladder','4mswMCGv9CI'],
  tracker:['The Toning Ladder tracker','LMCfF7X2mwY'],
  calU35:['Plug & Play calendar, under 35','fgXcAGJjlTw'],
  calO35:['Plug & Play calendar, over 35','T4k9JNr2iqY'],
  spice:['The Spice Rack system','THl7nW9WPT8'],
  journal:['The Vault Journal','sBJ1A5HxmL8'],
};
// A "Watch Michelle explain" button that opens the video in place. Call renderVid(key) for the html and
// put data-vid on a container; clicks toggle it.
const vidOpen={};
function vidHTML(key,label){
  const v=VIDS[key];if(!v)return '';
  const id=v[1],text=label||v[0];
  if(!EMBED_OK) return `<a class="demo" href="https://www.youtube.com/watch?v=${id}" target="_blank" rel="noopener">▶ ${esc(text)}</a>`;
  return vidOpen[key]?`<div class="vid"><div class="embed"><iframe src="https://www.youtube-nocookie.com/embed/${id}?rel=0&modestbranding=1&playsinline=1&autoplay=1" title="${esc(text)}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe></div><button class="demo" data-vid="${key}">✕ Close video</button></div>`
    :`<div class="vid"><button class="demo" data-vid="${key}">▶ ${esc(text)}</button></div>`;
}
document.addEventListener('click',e=>{const b=e.target.closest('button[data-vid]');if(!b)return;vidOpen[b.dataset.vid]=!vidOpen[b.dataset.vid];
  const html=vidHTML(b.dataset.vid,b.textContent.replace(/^[▶✕]\s*(Close video)?/,'').trim()||undefined);const wrap=b.closest('.vid');if(wrap){wrap.outerHTML=html}});
function pairFor(d,v){return d.pairs&&d.pairs.includes(v)?{startPhoto:`images/${v}-start.webp`,endPhoto:`images/${v}-end.webp`}:{}}
function picHTML(d,e,lazy){
  const v=e.video; const pr=e.startPhoto?{startPhoto:e.startPhoto,endPhoto:e.endPhoto}:pairFor(d,v);
  if(pr.startPhoto) return `<div class="pair"><figure><img src="${esc(pr.startPhoto)}" alt="" ${lazy?'loading="lazy"':''}><figcaption>Start</figcaption></figure><figure><img src="${esc(pr.endPhoto)}" alt="" ${lazy?'loading="lazy"':''}><figcaption>End</figcaption></figure></div>`;
  return e.photo?`<img class="photo" src="${esc(e.photo)}" alt="" ${lazy?'loading="lazy"':''}>`:'';
}

/* ---- applying today's spice to the workout ----
   The bones stay the same. The spice changes only how the reps are done, on every exercise or on the last
   exercise of each circuit, whichever was picked on the Spice Rack page. */
function spiceToday(){const s=store.get('vault:spice',null);return s&&s.d===TODAY?s:null}
function spiced(e,lastInBlock){
  const sp=spiceToday(); if(!sp) return e;
  if((sp.scope||'last')==='last'&&!lastInBlock) return e;
  const x={...e,spice:sp.name};
  switch(sp.id){
    case 'drop': x.reps='10-10-10'; x.spiceNote='Drop set: 10 reps heavy, drop the weight, 10 more, drop again, 10 more. No rest between drops.'; break;
    case 'pyramid': x.reps='10-10-10-10-10'; x.sets=1; x.restSeconds=Math.max(e.restSeconds,60); x.spiceNote='Pyramid: 10 reps, go up in weight, 10 more, up again, 10 more. Rest 10 seconds, then 10 and 10 back down. One big set.'; break;
    case '21': x.reps='7-7-7'; x.spiceNote="21's: 7 bottom half, 7 top half, 7 full range. No rest between the parts."; break;
    case 'half': x.spiceNote='1½ reps: all the way down, halfway up, back down, all the way up. That is one rep. Same rep count.'; break;
    case 'neg': x.tempo='512'; x.spiceNote='Negatives: 5 to 6 seconds down, pause 1, up in 2. Same reps, slower.'; break;
    case 'iso': x.note=((e.note||'')+' Isometric Hold 25s').trim(); x.spiceNote='Isometric hold: on the last rep, hold the hardest point for 20 to 30 seconds. Tap the hold timer.'; break;
    case 'uni': x.reps=/per side/.test(e.reps||'')?e.reps:(e.reps||'')+' per side'; x.spiceNote='One side at a time, or alternate. Equal reps each side.'; break;
  }
  return x;
}
const spiceBox=e=>e.spice?`<div class="spice">✦ <b>${esc(e.spice)} on this one.</b> ${esc(e.spiceNote||'')}</div>`:'';
