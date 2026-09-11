/** Rebuild the editorial deck from the unchanged Phase 13.3 presentation.
 * Required environment: RUNTIME_NODE_MODULES, RUNTIME_PYTHON, PPT_SKILL_DIR.
 * Run with the bundled Node executable. Final promotion follows validation.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const {RUNTIME_NODE_MODULES,RUNTIME_PYTHON,PPT_SKILL_DIR}=process.env;
if(!RUNTIME_NODE_MODULES||!RUNTIME_PYTHON||!PPT_SKILL_DIR)throw Error('Set RUNTIME_NODE_MODULES, RUNTIME_PYTHON and PPT_SKILL_DIR from the bundled workspace runtime.');
const require=createRequire(import.meta.url);
const {FileBlob,PresentationFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool',{paths:[RUNTIME_NODE_MODULES]})).href);
const p=await PresentationFile.importPptx(await FileBlob.load(path.join(root,'outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pptx')));
const inspect=async()=> (await p.inspect({kind:'slide,textbox,shape',maxChars:500000})).ndjson.split('\n').filter(Boolean).map(JSON.parse);
const rows=await inspect();
const changes=JSON.parse(await fs.readFile(path.join(root,'reports/submission/presentation_changes.json'),'utf8'));
const anchors=[];
for(const c of changes){
 const found=rows.filter(r=>r.kind==='textbox'&&r.slide===c.slide&&r.text===c.old);
 if(found.length!==(c.count||1))throw Error(`Expected one textbox: ${JSON.stringify(c)}`);
 for(const match of found){
 const target=p.resolve(match.id);
 if(c.position)target.position=c.position;
 if(c.fontSizePt)target.text.style={fontSizePt:c.fontSizePt};
 // The API's replace does not span paragraph boundaries. Replace within each
 // existing paragraph to preserve its font, size and other text formatting.
 const oldLines=c.old.split('\n'),newLines=c.new.split('\n');
 if(oldLines.length!==newLines.length)throw Error('Paragraph count changed');
 for(let i=0;i<oldLines.length;i++)if(oldLines[i]!==newLines[i])target.text.replace(oldLines[i],newLines[i]);
 anchors.push({id:match.id,...c});
 }
}
const after=await inspect();
for(const c of anchors)if(after.find(r=>r.id===c.id)?.text!==c.new)throw Error('Text replacement failed: '+c.old);
// Keep the full 2:1 original dispatch plot above the existing caption strip.
const imageRows=(await p.inspect({kind:'image',maxChars:500000})).ndjson.split('\n').filter(Boolean).map(JSON.parse);
for(const r of imageRows.filter(r=>[9,20].includes(r.slide)&&r.kind==='image')){
 const img=p.resolve(r.id), pos=img.position;
 const width=pos.height*2400/1476;
 img.position={...pos,left:pos.left+(pos.width-width)/2,width};
}
const dispatchImages=imageRows.filter(r=>r.slide===19 && r.kind==='image');
if(dispatchImages.length!==1)throw Error('Expected one dispatch image: '+JSON.stringify(dispatchImages));
p.resolve(dispatchImages[0].id).position={left:95,top:180,width:720,height:360};
const dispatchSlide=p.slides.items[18];
for(const [left,top,width,height,text,fontSize] of [
 [95,180,720,26,'代表性测试调度：Hog_office_Joey，2017-12-14',14],
 [696,212,104,10.4,'实际负荷',8.5],
 [696,222.4,104,10.4,'决策选权重',8.5],
 [696,232.8,104,10.4,'预测选权重',8.5],
]){
 const box=dispatchSlide.shapes.add({geometry:'textbox',position:{left,top,width,height},fill:'#FFFFFF',line:{fill:'none',width:0}});
 box.text=text;box.text.style={typeface:'Microsoft YaHei',fontSize,color:'#18212B',autoFit:'none',alignment:top===180?'center':'left',verticalAlignment:'middle',insets:{left:0,right:0,top:0,bottom:0}};
}
const build=path.join(root,'tmp/competition_style','build-'+Date.now());
const supplements=JSON.parse(await fs.readFile(path.join(root,'reports/submission/presentation_supplements.json'),'utf8'));
// Native application diagram replaces the conceptual image on slide 3.
// The old media bytes stay in the package for historical identity checks.
const applicationSlide=p.slides.items[2];
const applicationTexts=[];
const applicationText=(left,top,width,height,text,size,color='#18212B',fill='none')=>{
 const box=applicationSlide.shapes.add({geometry:'textbox',position:{left,top,width,height},fill,line:{fill:'none',width:0}});
 box.text=text;box.text.style={typeface:'Microsoft YaHei',fontSize:size,color,alignment:'center',verticalAlignment:'middle',autoFit:'none',insets:{left:3,right:3,top:2,bottom:2}};
 applicationTexts.push(text);
};
const stages=[['智能电表 / EMS','历史小时级负荷','现场接入待实现'],['智储云控','DOEF 负荷预测','离线预测已实现'],['储能优化','24 h 充放电计划','约束求解已实现'],['储能系统','充电 / 放电','设备执行待实现'],['建筑电网侧','评价最大取电功率','已完成仿真评价']];
for(let i=0;i<stages.length;i++){
 const x=108+i*216;
 applicationText(x,278,188,44,stages[i][0],23);
 applicationText(x,326,188,46,stages[i][1],18);
 applicationText(x,382,188,34,stages[i][2],16,i===0||i===3?'#A65E10':'#087BA5');
 if(i<4)applicationText(x+188,316,28,40,'→',24);
}
applicationText(134,446,1010,42,'评价反馈：实际负荷与执行回执 → 核对峰值、执行偏差与异常',21);
applicationText(134,498,1010,32,'当前：冻结实验回放；未来：接入电表、EMS 与 PCS/BMS',18,'#526373');
supplements.diagram_texts={'3':applicationTexts};
await fs.writeFile(path.join(root,'reports/submission/presentation_supplements.json'),JSON.stringify(supplements,null,2)+'\n');
for(const [number,text] of Object.entries(supplements.notes))p.slides.items[Number(number)-1].speakerNotes.textFrame.setText(text);
await fs.mkdir(path.join(build,'final'),{recursive:true});
const candidatePath=path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidatePath);
execFileSync(RUNTIME_PYTHON,[path.join(root,'reports/submission/localize_figures.py'),'--pptx',candidatePath],{cwd:root,stdio:'inherit'});
const {finalizePresentation}=await import(pathToFileURL(path.join(PPT_SKILL_DIR,'container_tools/artifact_tool_utils.mjs')).href);
const finalPath=path.join(build,'final','DOEF_Competition_Presentation.pptx');
const result=await finalizePresentation({workspaceDir:root,candidatePath,finalPath,pythonExecutable:RUNTIME_PYTHON,integrityValidatorPath:path.join(PPT_SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(PPT_SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000'],explicitTotalSlideCount:23,requiredNativeTableOwnerSlides:[],verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});
await fs.mkdir(path.join(root,'outputs/submission'),{recursive:true});
await fs.copyFile(finalPath,path.join(root,'outputs/submission/DOEF_Competition_Presentation.pptx'));
await fs.mkdir(path.join(root,'reports/submission/qa'),{recursive:true});
await fs.writeFile(path.join(root,'reports/submission/qa/presentation_package.json'),JSON.stringify({status:'PASS',changed_textboxes:changes.length,slide_count:23,package_findings:result.packageIntegrity.finding_count,layout_findings:result.presentationLayout.finding_count,layout_warnings:result.presentationLayout.warning_count,source_native_table_count:0,table_implementation:'Original editable textboxes and shapes retained',first_party_import:result.firstPartyImport,sha256:(await import('node:crypto')).createHash('sha256').update(await fs.readFile(path.join(root,'outputs/submission/DOEF_Competition_Presentation.pptx'))).digest('hex')},null,2)+'\n');
console.log('PPTX validated and promoted; export PDF and visually check before release.');
