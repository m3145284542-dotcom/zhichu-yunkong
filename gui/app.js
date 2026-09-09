'use strict';
let data, page = 2;
let tourActive=false, tourPaused=false, tourIndex=0, tourElapsed=0, tourLast=0, tourFrame=null, replayPaint=null;
const TOUR_SECONDS=4;
const TOUR_DRAW_SECONDS=2.5;
const scripts = {2:'点击开始巡演，自动展示八栋建筑的调度曲线与运行总览，约32秒后停在综合结果。',3:'八建筑结果与平均效果汇总。结论限定于当前离线实验范围。'};
const $ = id => document.getElementById(id);
const fmt = (n, digits = 2) => Number(n).toFixed(digits);
const card = (label, value, unit, hint) => `<article class="card"><div class="label">${label}</div><div class="value">${value}<small>${unit}</small></div><div class="hint">${hint}</div></article>`;
const detail = (a,b) => `<div class="detail"><span>${a}</span><strong>${b}</strong></div>`;
let replayFrame = null, replayDay = 0, replayRunning = false, replayLast = 0, replaySpeed = 12;
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function animateCards(){
  if(reducedMotion)return;
  document.querySelectorAll('.card .value').forEach(el=>{
    const node=el.firstChild, end=Number(node.textContent), decimals=(node.textContent.split('.')[1]||'').length;
    if(!Number.isFinite(end)||el.closest('.building-snapshot'))return;
    const begin=performance.now();
    function tick(now){if(!el.isConnected)return;const p=Math.min(1,(now-begin)/850);node.textContent=(end*(1-Math.pow(1-p,3))).toFixed(decimals);if(p<1)requestAnimationFrame(tick);}
    requestAnimationFrame(tick);
  });
}
function getDaily(building){
  const doef=data.daily.filter(r=>r.building===building&&r.method==='DecisionSelectedPerBuilding').sort((a,b)=>a.date.localeCompare(b.date));
  const light=new Map(data.daily.filter(r=>r.building===building&&r.method==='LightGBM').map(r=>[r.date,r]));
  return doef.map(r=>({date:r.date,before:+r.original_peak,doef:+r.realized_peak,light:+light.get(r.date).realized_peak}));
}
function replayPage(building){
  const metric=data.metrics.find(r=>r.building===building&&r.method==='Phase8_DOEF'&&r.split==='test');
  const battery=data.battery.find(r=>r.building===building), weight=data.weights.find(r=>r.building===building);
  const overview=`<section class="building-snapshot"><div class="snapshot-heading"><h3>${building.split('_').pop()} · 运行总览</h3><span>整个测试期 · 30 天</span></div><div class="cards current-cards">${card('无储能峰值',fmt(metric.no_battery_peak),'kW','调度前')}${card('DOEF 调度后峰值',fmt(metric.post_dispatch_peak),'kW','调度后')}${card('峰值降低量',fmt(metric.absolute_peak_reduction),'kW','负值表示峰值增加')}${card('整段削峰率',fmt(metric.peak_reduction_percentage),'%','当前建筑')}</div><div class="config-strip"><span>电池容量 <b>${fmt(battery.capacity)} kWh</b></span><span>充 / 放电上限 <b>${fmt(battery.max_charge_power)} kW</b></span><span>LightGBM 权重 <b>${fmt(weight.w_decision,1)}</b></span><span>SOC <b>10% – 90%</b></span><span>往返效率 <b>90%</b></span></div></section>`;
  return `<div class="replay-heading"><div><span class="eyebrow">BEFORE / AFTER · 30-DAY REPLAY</span><h2>从负荷峰值，到削峰结果</h2><p class="hint">${building} · 2017-12-02 至 12-31 · 每个点代表一天的最大取电功率，不是小时负荷。</p></div><span class="badge"><span class="dot"></span> 真实实验回放</span></div>
  <div class="replay-grid"><article class="panel replay-main"><div class="chart-top"><h2>调度前后 · 日峰值对比</h2><strong id="replay-date">12-02</strong></div><div id="replay-chart"></div>
  <div class="toggle-legend"><label><input type="checkbox" data-series="before" checked><i style="background:#9aa7b5"></i>无储能</label><label><input type="checkbox" data-series="light" checked><i style="background:#5982de"></i>LightGBM 调度</label><label><input type="checkbox" data-series="doef" checked><i style="background:#0aa993"></i>DOEF 调度</label></div>
  ${overview}
  <div class="transport"><button id="replay-toggle" class="primary">Ⅱ 暂停回放</button><button id="replay-reset" aria-label="重播30天">↺ 重播</button><label>速度 <select id="replay-speed" aria-label="回放速度"><option value="4">4×</option><option value="8">8×</option><option value="12" selected>12×</option></select></label><span class="hint" id="day-counter">01 / 30 天</span></div>
  <input id="timeline" type="range" min="0" max="29" value="0" step="1" aria-label="回放日期"><div class="timeline-labels"><span>12 月 02 日</span><span>拖动时间轴，检查任意一天</span><span>12 月 31 日</span></div></article>
  <article class="panel replay-side"><span class="eyebrow">DAILY COMPARISON</span><h2>当天削峰效果</h2><div class="peak-values"><div><span>无储能日峰值</span><strong id="before-value">—</strong><small>kW</small></div><span class="compare-arrow">→</span><div><span>DOEF 日峰值</span><strong id="after-value">—</strong><small>kW</small></div></div>
  <div id="saving-box" class="saving"><span id="saving-title">当天峰值降低</span><strong id="saving-value">—</strong><span id="saving-percent"></span></div>
  <div class="daily-bars" id="daily-bars"></div><p class="hint" id="method-delta"></p><div class="note">日峰值来自各自调度曲线的最大值，出现时刻可能不同。此动画回放已有实验，不表示正在重新求解。</div></article></div>`;
}
function setupReplay(building){
  const rows=getDaily(building), series=[{key:'before',color:'#9aa7b5'},{key:'light',color:'#5982de'},{key:'doef',color:'#0aa993'}];
  const w=800,h=310,l=62,r=22,t=28,b=38;
  const values=rows.flatMap(r=>[r.before,r.light,r.doef]);
  const lo=Math.floor(Math.min(...values)*.92),hi=Math.max(...values)*1.06;
  const x=i=>l+i*(w-l-r)/29, y=v=>h-b-(v-lo)/(hi-lo)*(h-t-b);
  let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="无储能、LightGBM 与 DOEF 的30天日峰值动态对比"><defs><clipPath id="reveal-clip"><rect id="reveal-rect" x="${l-6}" y="0" width="6" height="${h}"/></clipPath></defs><text x="${l}" y="14">日峰值 / kW</text>`;
  for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4;svg+=`<line x1="${l}" x2="${w-r}" y1="${y(v)}" y2="${y(v)}" stroke="#e8edf2"/><text x="${l-8}" y="${y(v)+4}" text-anchor="end">${fmt(v,0)}</text>`;}
  [0,5,10,15,20,25,29].forEach(i=>svg+=`<text x="${x(i)}" y="${h-10}" text-anchor="middle">${rows[i].date.slice(5)}</text>`);
  series.forEach(s=>svg+=`<g data-plot="${s.key}" clip-path="url(#reveal-clip)"><polyline fill="none" stroke="${s.color}" stroke-width="${s.key==='doef'?3.5:2}" points="${rows.map((v,i)=>`${x(i)},${y(v[s.key])}`).join(' ')}"/>${rows.map((v,i)=>`<circle cx="${x(i)}" cy="${y(v[s.key])}" r="3" fill="${s.color}"><title>${v.date}: ${fmt(v[s.key])} kW</title></circle>`).join('')}</g>`);
  svg+=`<line id="day-cursor" y1="${t}" y2="${h-b}" stroke="#087f8c" stroke-dasharray="4 5"/>`;
  series.forEach(s=>svg+=`<circle id="point-${s.key}" r="6" fill="${s.color}" stroke="white" stroke-width="2"/>`);
  $('replay-chart').innerHTML=svg+'</svg>';
  replayDay=0; replayLast=0; replaySpeed=12; replayRunning=false;
  let lastPaintedDay=-1;
  function paint(){
    const i=Math.min(29,Math.floor(replayDay)),row=rows[i];
    $('reveal-rect').setAttribute('width',x(replayDay)-l+12);
    $('day-cursor').setAttribute('x1',x(replayDay));$('day-cursor').setAttribute('x2',x(replayDay));
    series.forEach(s=>{const value=row[s.key]+((rows[Math.min(i+1,29)][s.key]-row[s.key])*(replayDay-i));$('point-'+s.key).setAttribute('cx',x(replayDay));$('point-'+s.key).setAttribute('cy',y(value));});
    $('replay-toggle').textContent=replayRunning?'Ⅱ 暂停回放':(replayDay>=29?'↺ 再次播放':'▶ 继续回放');
    if(lastPaintedDay===i)return;
    lastPaintedDay=i;
    $('timeline').value=i;$('replay-date').textContent=row.date;$('day-counter').textContent=`${String(i+1).padStart(2,'0')} / 30 天`;
    $('before-value').textContent=fmt(row.before);$('after-value').textContent=fmt(row.doef);
    const saving=row.before-row.doef;
    $('saving-title').textContent=saving>=0?'当天峰值降低':'当天峰值增加 · 反向削峰';
    $('saving-value').textContent=fmt(Math.abs(saving))+' kW';
    $('saving-percent').textContent='当天削峰率 '+fmt(saving/row.before*100)+'%';
    $('saving-box').classList.toggle('negative',saving<0);
    const max=Math.max(row.before,row.light,row.doef);
    $('daily-bars').innerHTML=[['无储能',row.before,'#9aa7b5'],['LightGBM',row.light,'#5982de'],['DOEF',row.doef,'#0aa993']].map(([label,v,color])=>`<div class="bar-label"><span>${label}</span><strong>${fmt(v)} kW</strong></div><div class="bar-track"><div style="width:${v/max*100}%;background:${color}"></div></div>`).join('');
    const delta=row.light-row.doef;
    $('method-delta').textContent=`相比 LightGBM，当天 DOEF 峰值${delta>=0?'降低':'增加'} ${fmt(Math.abs(delta))} kW。`;
  }
  function tick(now){
    if(page!==2||!$('timeline'))return;
    if(replayRunning&&replayLast){replayDay=Math.min(29,replayDay+(now-replayLast)/1000*replaySpeed);if(replayDay>=29)replayRunning=false;}
    replayLast=now;paint();
    if(replayRunning)replayFrame=requestAnimationFrame(tick);
  }
  function resume(){cancelAnimationFrame(replayFrame);replayLast=0;replayRunning=true;replayFrame=requestAnimationFrame(tick);}
  $('replay-toggle').onclick=()=>{if(replayRunning){replayRunning=false;cancelAnimationFrame(replayFrame);paint();}else{if(replayDay>=29)replayDay=0;resume();}};
  $('replay-reset').onclick=()=>{replayDay=0;resume();};
  $('timeline').oninput=()=>{replayRunning=false;cancelAnimationFrame(replayFrame);replayDay=+$('timeline').value;paint();};
  $('replay-speed').onchange=()=>{replaySpeed=+$('replay-speed').value;};
  document.querySelectorAll('[data-series]').forEach(input=>input.onchange=()=>{document.querySelector(`[data-plot="${input.dataset.series}"]`).style.opacity=input.checked?'1':'0';$('point-'+input.dataset.series).style.opacity=input.checked?'1':'0';});
  replayPaint=paint;
  ['replay-toggle','replay-reset','replay-speed','timeline'].forEach(id=>$(id).disabled=tourActive);
  paint();if(replayRunning)replayFrame=requestAnimationFrame(tick);
}
function updateTourUI(){
  $('tour-panel').hidden=!tourActive;
  $('tour').textContent=tourActive?(tourPaused?'▶ 继续巡演':'Ⅱ 暂停巡演'):(page===3?'↺ 重新巡演':'▶ 开始巡演');
  if(!tourActive)return;
  $('tour-pause').textContent=tourPaused?'▶ 继续':'Ⅱ 暂停';
  $('tour-status').textContent=`${tourPaused?'已暂停 · ':''}第 ${tourIndex+1} / 8 栋 · ${data.algorithm.fixed_buildings[tourIndex].split('_').pop()}`;
  $('tour-buildings').innerHTML=data.algorithm.fixed_buildings.map((b,i)=>`<span class="${i<tourIndex?'done':i===tourIndex?'current':''}">${i<tourIndex?'✓':String(i+1).padStart(2,'0')} ${b.split('_').pop()}</span>`).join('');
}
function stopTour(){
  tourActive=false;tourPaused=false;cancelAnimationFrame(tourFrame);tourFrame=null;
  updateTourUI();
  ['replay-toggle','replay-reset','replay-speed','timeline'].forEach(id=>{if($(id))$(id).disabled=false;});
}
function showTourBuilding(){
  tourElapsed=0;tourLast=0;
  $('building').value=data.algorithm.fixed_buildings[tourIndex];
  go(2);updateTourUI();
  $('replay-toggle').textContent='巡演自动回放';
  $('narration').textContent=`第 ${tourIndex+1} 栋：${data.algorithm.fixed_buildings[tourIndex].split('_').pop()}。灰线为无储能日峰值，蓝线为 LightGBM，绿线为 DOEF；曲线播放完毕后自动切换下一栋。`;
}
function nextTourBuilding(){
  if(tourIndex===data.algorithm.fixed_buildings.length-1){
    stopTour();go(3);updateTourUI();
    $('narration').textContent='八栋建筑巡演完成。以下汇总完整建筑结果和平均效果，保留未改善及反向削峰的情况。';
    return;
  }
  tourIndex++;showTourBuilding();
}
function tourTick(now){
  if(!tourActive)return;
  if(!tourPaused){
    if(tourLast)tourElapsed+=Math.min((now-tourLast)/1000,.25);
    // Draw quickly, then hold the complete curve with the building overview.
    replayDay=Math.min(29,tourElapsed/TOUR_DRAW_SECONDS*29);
    if(replayPaint)replayPaint();
    $('replay-toggle').textContent='巡演自动回放';
    $('tour-progress').style.width=`${(tourIndex+Math.min(1,tourElapsed/TOUR_SECONDS))/8*100}%`;
    if(tourElapsed>=TOUR_SECONDS)nextTourBuilding();
  }
  tourLast=now;
  if(tourActive)tourFrame=requestAnimationFrame(tourTick);
}
function toggleTourPause(){
  tourPaused=!tourPaused;tourLast=0;updateTourUI();
}
function startTour(){
  if(!data)return;
  if(tourActive){toggleTourPause();return;}
  tourActive=true;tourPaused=false;tourIndex=0;
  showTourBuilding();$('tour-progress').style.width='0%';
  window.scrollTo({top:0,behavior:'instant'});
  tourFrame=requestAnimationFrame(tourTick);
}
function addComparison(doef,lgb){
  const groups=[['平均归一化预测 MAE','normalized_mae_mean'],['平均归一化决策后悔值','normalized_decision_regret_mean']];
  const html=`<article class="panel aggregate-compare"><div><span class="eyebrow">ALGORITHM COMPARISON</span><h2>LightGBM → DOEF：预测与决策同时比较</h2><p class="hint">同一批八建筑、相同电池配置；两项指标均为越低越好。</p></div><div class="comparison-pairs">${groups.map(([name,key])=>`<div><h3>${name}</h3>${[['LightGBM',+lgb[key],'#5982de'],['DOEF',+doef[key],'#0aa993']].map(([label,value,color])=>`<div class="bar-label"><span>${label}</span><strong>${fmt(value,5)}</strong></div><div class="bar-track"><div class="grow-bar" style="width:${value/Math.max(+lgb[key],+doef[key])*100}%;background:${color}"></div></div>`).join('')}<p class="positive">改善 ${fmt((1-doef[key]/lgb[key])*100)}%</p></div>`).join('')}</div></article>`;
  const cards=document.querySelector('#content .cards');
  cards.remove();
  $('content').insertAdjacentHTML('beforeend',html);
  $('content').appendChild(cards);
  $('content').insertAdjacentHTML('beforeend', '<div class="method-recap"><strong>DOEF：w × LightGBM + (1 − w) × DayWeek</strong><span>逐建筑权重仅在验证集按调度后悔值选择，测试期冻结。</span><span>统一电池约束：容量为训练期平均日用电量的10%；SOC 10%–90%；每日初始/终止50%；往返效率90%。</span></div>');
}
function render() {
  if(!data)return;
  cancelAnimationFrame(replayFrame); replayFrame = null;
  const building=$('building').value;
  const weight=data.weights.find(r=>r.building===building), battery=data.battery.find(r=>r.building===building);
  const doef=data.benchmark.find(r=>r.display_name==='DOEF'), lgb=data.benchmark.find(r=>r.display_name==='LightGBM');
  const metric=data.metrics.find(r=>r.building===building && r.method==='Phase8_DOEF' && r.split==='test');
  $('content').classList.toggle('final-summary',page===3);
  $('title').textContent=page===3?'综合结果':'八建筑巡演';$('step').textContent=page===3?'巡演完成':'曲线与运行总览';$('current-building').textContent=building.split('_').pop();$('narration').textContent=scripts[page];
  let html='';
  if(page===2){
    html = replayPage(building);
  }else{
    const buildings=data.algorithm.fixed_buildings;
    const rows=buildings.map(b=>({b,d:data.metrics.find(r=>r.building===b&&r.method==='Phase8_DOEF'&&r.split==='test'),l:data.metrics.find(r=>r.building===b&&r.method==='LightGBM'&&r.split==='test'),mean:data.battery.find(r=>r.building===b).mean_train_load}));
    html=`<div class="cards">${card('决策后悔值改善',doef.decision_wins_vs_lightgbm,'栋','相对 LightGBM')}${card('决策后悔值持平',doef.decision_ties_vs_lightgbm,'栋','完整展示固定八建筑')}${card('平均整段削峰率',fmt(doef.peak_reduction_mean_pct),'%','八建筑等权平均')}${card('最小整段削峰率',fmt(doef.peak_reduction_min_pct),'%','保留反向削峰结果')}</div><article class="panel"><h2>逐建筑对比：决策后悔值越低越好</h2><table><thead><tr><th>建筑</th><th>无储能峰值 / kW</th><th>DOEF 峰值 / kW</th><th>LightGBM 归一化后悔值</th><th>DOEF 归一化后悔值</th><th>DOEF 整段削峰率</th></tr></thead><tbody>${rows.map(r=>`<tr class="${r.b===building?'selected-row':''}"><td>${r.b}</td><td>${fmt(r.d.no_battery_peak)}</td><td>${fmt(r.d.post_dispatch_peak)}</td><td>${fmt(r.l.mean_regret_vs_oracle/r.mean,5)}</td><td>${fmt(r.d.mean_regret_vs_oracle/r.mean,5)}</td><td>${fmt(r.d.peak_reduction_percentage)}%</td></tr>`).join('')}</tbody></table><div class="source">来源：outputs/phase9/per_building_metrics.csv · 归一化分母：outputs/phase7/building_battery_configs.csv</div></article>`;
  }
  $('content').innerHTML=html;
  animateCards();
  if(page===2) setupReplay(building);
  if(page===3) addComparison(doef,lgb);
}
function go(p){page=p===3?3:2;render();}

$('tour').onclick=startTour;
$('tour-pause').onclick=toggleTourPause;
$('tour-next').onclick=()=>{tourLast=0;nextTourBuilding();};
$('tour-exit').onclick=()=>{stopTour();render();};
$('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{$('narration').textContent='浏览器未允许全屏，可按 F11 进入录屏视图。';}};
document.addEventListener('fullscreenchange',()=>{$('fullscreen').textContent=document.fullscreenElement?'⛶ 退出全屏':'⛶ 全屏';});
document.addEventListener('keydown',e=>{if(['SELECT','INPUT','TEXTAREA','BUTTON'].includes(e.target.tagName))return;if(e.key==='ArrowRight'){if(tourActive)$('tour-next').click();}if(e.code==='Space'){e.preventDefault();if(tourActive)toggleTourPause();else $('tour').click();}});
(document.getElementById('demo-data') ? Promise.resolve(JSON.parse(document.getElementById('demo-data').textContent)) : fetch('/api/demo').then(r=>{if(!r.ok)throw Error('无法读取实验源文件');return r.json();})).then(d=>{data=d;$('building').innerHTML=data.algorithm.fixed_buildings.map(b=>`<option>${b}</option>`).join('');render();}).catch(e=>{$('content').textContent=`载入失败：${e.message}。请检查源文件并重新启动 gui/server.py。`;['tour','building'].forEach(id=>$(id).disabled=true);});
