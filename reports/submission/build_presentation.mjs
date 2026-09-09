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
 if(found.length!==1)throw Error(`Expected one textbox: ${JSON.stringify(c)}`);
 const target=p.resolve(found[0].id);
 if(c.position)target.position=c.position;
 if(c.fontSizePt)target.text.style={fontSizePt:c.fontSizePt};
 // The API's replace does not span paragraph boundaries. Replace within each
 // existing paragraph to preserve its font, size and other text formatting.
 const oldLines=c.old.split('\n'),newLines=c.new.split('\n');
 if(oldLines.length!==newLines.length)throw Error('Paragraph count changed');
 for(let i=0;i<oldLines.length;i++)if(oldLines[i]!==newLines[i])target.text.replace(oldLines[i],newLines[i]);
 anchors.push({id:found[0].id,...c});
}
const after=await inspect();
for(const c of anchors)if(after.find(r=>r.id===c.id)?.text!==c.new)throw Error('Text replacement failed: '+c.old);
const build=path.join(root,'tmp/competition_style','build-'+Date.now());
await fs.mkdir(path.join(build,'final'),{recursive:true});
const candidatePath=path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidatePath);
const {finalizePresentation}=await import(pathToFileURL(path.join(PPT_SKILL_DIR,'container_tools/artifact_tool_utils.mjs')).href);
const finalPath=path.join(build,'final','DOEF_Competition_Presentation.pptx');
const result=await finalizePresentation({workspaceDir:root,candidatePath,finalPath,pythonExecutable:RUNTIME_PYTHON,integrityValidatorPath:path.join(PPT_SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(PPT_SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000'],explicitTotalSlideCount:23,requiredNativeTableOwnerSlides:[],verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});
await fs.mkdir(path.join(root,'outputs/submission'),{recursive:true});
await fs.copyFile(finalPath,path.join(root,'outputs/submission/DOEF_Competition_Presentation.pptx'));
execFileSync(RUNTIME_PYTHON,[path.join(root,'reports/submission/localize_figures.py')],{cwd:root,stdio:'inherit'});
await fs.mkdir(path.join(root,'reports/submission/qa'),{recursive:true});
await fs.writeFile(path.join(root,'reports/submission/qa/presentation_package.json'),JSON.stringify({status:'PASS',changed_textboxes:changes.length,slide_count:23,package_findings:result.packageIntegrity.finding_count,layout_findings:result.presentationLayout.finding_count,layout_warnings:result.presentationLayout.warning_count,source_native_table_count:0,table_implementation:'Original editable textboxes and shapes retained',first_party_import:result.firstPartyImport,sha256:result.finalSha256},null,2)+'\n');
console.log('PPTX validated and promoted; export PDF and visually check before release.');
