// Exercise the real tour controller with a deterministic animation clock.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {textContent:'',innerHTML:'',value:'',style:{},hidden:true,currentTime:0,playing:false,play(){this.playing=true;return Promise.resolve();},pause(){this.playing=false;},setAttribute(){}});
  return nodes.get(id);
};
let clock=1000, serial=0;
const frames=new Map();
const context=vm.createContext({
  document:{getElementById:id=>id==='demo-data'?null:node(id),querySelectorAll:()=>[],addEventListener:()=>{}},
  window:{matchMedia:()=>({matches:false}),scrollTo:()=>{}},
  performance:{now:()=>clock},fetch:()=>new Promise(()=>{}),
  requestAnimationFrame:fn=>{frames.set(++serial,fn);return serial;},
  cancelAnimationFrame:id=>frames.delete(id),setInterval:()=>1,clearInterval:()=>{},console
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../gui/app.js'),'utf8'),context);
vm.runInContext(`data={algorithm:{fixed_buildings:['A','B','C','D','E','F','G','H']}};
  var seen=[], maxDays={}; render=function(){seen.push($('building').value);replayPaint=function(){const b=$('building').value;maxDays[b]=Math.max(maxDays[b]||0,replayDay);};};`,context);
const run = code=>vm.runInContext(code,context);
function step(count){for(let i=0;i<count;i++){clock+=100;const batch=[...frames.values()];frames.clear();batch.forEach(fn=>fn(clock));}}
run('startTour()');
assert.equal(node('building').value,'A');
step(10);
const position=run('tourElapsed');
run('toggleTourPause()');step(30);
assert.equal(run('tourElapsed'),position,'Pause must freeze the building clock');
run('toggleTourPause()');
let elapsed=0;
while(run('tourActive')&&elapsed<40000){step(1);elapsed+=100;}
assert.ok(elapsed<=33000,'Fast tour must finish within about 32 seconds of active playback');
assert.equal(run('tourActive'),false);
assert.equal(run('page'),3,'Tour must end on the evaluation page');
assert.deepEqual(Array.from(run('seen')).slice(0,8),['A','B','C','D','E','F','G','H']);
assert.deepEqual(Object.values(run('maxDays')),Array(8).fill(29),'Every curve must reach the final date before switching');
assert.equal(frames.size,0,'No tour animation should remain after completion');
run('startTour(); toggleTourPause(); nextTourBuilding()');
assert.equal(node('building').value,'B');
assert.equal(run('tourPaused'),true,'Skip must preserve paused state');
run('stopTour()');step(200);
assert.equal(node('building').value,'B','Exiting must prevent later automatic switches');
assert.equal(frames.size,0);
console.log('PASS: all eight buildings, pause/resume, skip, completion, cancellation');
