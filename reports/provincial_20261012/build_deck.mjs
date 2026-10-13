/** Provincial defense revision. Uses only frozen numerical evidence. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
const HERE=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(HERE,'../..');
const RUNTIME=process.env.CODEX_RUNTIME_DEPENDENCIES || 'C:/Users/m/.cache/codex-runtimes/codex-primary-runtime/dependencies';
process.env.RUNTIME_NODE_MODULES=RUNTIME+'/node/node_modules';
const SKILL=process.env.CODEX_PRESENTATIONS_SKILL || 'C:/Users/m/.codex/plugins/cache/openai-primary-runtime/presentations/26.1011.11113/skills/presentations';
const require=createRequire(import.meta.url);
const {FileBlob,PresentationFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool',{paths:[RUNTIME+'/node/node_modules']})).href);
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(SKILL+'/container_tools/artifact_tool_utils.mjs').href);
const E=JSON.parse(await fs.readFile(path.join(HERE,'evidence.json'),'utf8'));
const BUILD=path.join(ROOT,'tmp/provincial_review/build-'+Date.now());
const OUT=path.join(ROOT,'outputs/provincial_20261012');
await fs.mkdir(BUILD,{recursive:true});await fs.mkdir(OUT,{recursive:true});
const p=await PresentationFile.importPptx(await FileBlob.load(path.join(ROOT,'outputs/provincial_20261012/DOEF_Provincial_Submission.pptx')));
await fs.writeFile(path.join(BUILD,'source-inspect.ndjson'),(await p.inspect({kind:'slide,layout,textbox,image',maxChars:400000})).ndjson);
// The user requested a full restructuring. Preserve the imported theme, masters,
// 16:9 size and font palette; replace the redundant 23-slide narrative.
p.slides.keep([]);
const C={dark:'#081522',ink:'#142B40',muted:'#5A6D80',blue:'#007FAB',cyan:'#18BDEA',purple:'#7854B5',orange:'#BD6517',light:'#F5F8FC',line:'#D8E3ED',white:'#FFFFFF',pale:'#E8F4FA'};
const FONT='Microsoft YaHei';
const notes=[];
function text(s,t,x,y,w,h,size=26,color=C.ink,bold=false,align='left'){
 const q=s.shapes.add({geometry:'textbox',name:t.slice(0,35),position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 q.text=t;q.text.style={typeface:FONT,fontSize:size,color,bold,alignment:align,verticalAlignment:'middle',autoFit:'none',insets:{left:0,right:0,top:0,bottom:0}};return q;
}
function line(s,x,y,w,color=C.line){s.shapes.add({geometry:'line',position:{left:x,top:y,width:w,height:0},fill:'none',line:{fill:color,width:1}});}
function card(s,label,value,x,w,fill,color){
 s.shapes.add({geometry:'rect',position:{left:x,top:185,width:w,height:96},fill,line:{fill:'none',width:0}});
 text(s,label,x+18,194,w-36,30,22,color,true);
 text(s,value,x+18,228,w-36,43,34,color,true);
}
function slide(title,section,source='',dark=false){
 const s=p.slides.add();s.background.fill=dark?C.dark:C.light;
 const i=p.slides.items.length;
 s._cornerNotes=[section,source].filter(Boolean).join('\n');
 text(s,title,58,77,1160,65,38,dark?C.white:C.ink,true);
 line(s,58,154,1164,dark?'#244054':C.line);
 text(s,String(i).padStart(2,'0'),1166,662,54,28,15,dark?'#9AAFC0':C.muted,false,'right');
 return s;
}
function note(s,t,refs=[]){const full=t+(s._cornerNotes?'\n\n页面补充说明：\n'+s._cornerNotes:'')+'\n\n证据来源：\n'+refs.join('\n');s.speakerNotes.textFrame.setText("参考来源：\n"+refs.join("\n"));notes.push({slide:p.slides.items.length,title:titles[p.slides.items.length-1]||'',text:full});}
function table(s,values,x,y,width,height,widths,options={}){
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width,height,columnWidths:widths,values});
 t.styleOptions={headerRow:false,bandedRows:false};
 t.borders.assign({fill:C.line,width:.6,style:'solid'});
 const range=t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length});
 range.assign({margins:{left:14,right:14,top:7,bottom:7},anchor:'center'});
 for(let r=0;r<values.length;r++){
  t.rows[r].height=height/values.length;
  for(let c=0;c<values[r].length;c++){
   const cell=t.getCell(r,c);cell.fill=r===0?C.ink:(r===options.highlightRow?C.pale:(r%2?C.white:'#EDF2F7'));
   cell.text.style={typeface:FONT,fontSize:options.size||23,color:r===0?C.white:(r===options.highlightRow?C.blue:C.ink),bold:r===0||r===options.highlightRow,alignment:c===0?'left':'center',verticalAlignment:'middle'};
  }
 }
 return t;
}
async function pic(s,relative,x,y,w,h,crop){const b=await fs.readFile(path.join(ROOT,relative));s.images.add({blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',alt:'智储云控现有离线仿真界面',position:{left:x,top:y,width:w,height:h},fit:crop?'cover':'contain',...(crop?{crop}:{})});}
function chartFont(chart){applyPresentationChartFont(chart,{fontFamily:FONT});}
function num(v,n=6){return Number(v).toFixed(n);}
const titles=[
 '智储云控','项目背景与行业痛点','核心问题：预测误差最优 ≠ 削峰决策最优','项目创新点：方法改进与工程贡献','技术方案：DOEF 决策导向预测融合','实验设计：8 栋办公楼，30 个测试日','实验结果：相对 LightGBM，平均误差与后悔值均降低','消融实验：选权目标与逐楼适配均有增益','局限性分析：平均改善仍有失效边界','系统展示：离线仿真回放与结果比较','应用价值：辅助比较建筑储能削峰方案','总结与展望：方法、结果与适用边界','附录：完整基准与统计口径','附录：融合权重与电池约束','附录：指标定义与评价口径','附录：完整消融、复现与参考依据'].slice(0,12).map((title,i)=>i===0?title:`${String(i).padStart(2,'0')} ${title}`);
let s;
// 1. Cover, preserving the project identity without repeated subtitles.
s=slide(titles[0],'全球校园人工智能算法精英大赛 · AI+能源科技创新组','团队编号：AIC-2026-27833449',true);
text(s,'基于决策导向预测融合的\n建筑储能削峰优化系统',58,197,1150,150,48,C.white,true);
text(s,'用调度后的削峰表现，选择负荷预测组合',60,384,1140,65,31,C.cyan);
line(s,60,495,1155,'#244054');
text(s,'算法方法  DOEF',60,526,540,42,24,C.white,true);
text(s,'验证范围  8 栋办公楼的离线仿真',620,526,570,42,24,C.white,true);
text(s,'第八届全球校园人工智能算法精英大赛 · AI+能源科技创新组',60,591,1140,30,22,'#ACBDCC');
text(s,'团队：电协    团队编号：AIC-2026-27833449',60,629,1100,28,21,'#ACBDCC');
note(s,'各位评委老师好，我们的作品是智储云控。我们关注办公楼储能的一个具体问题：预测结果是否真正帮助电池降低用电峰值。本作品完成了决策导向预测融合、约束调度和离线结果展示。建议 20 秒。',['README.md','outputs/phase9_1/final_reporting_summary.json']);
// 2. Industry pain point.
s=slide(titles[1],'背景与需求','场景解释，不代表已部署案例；当前对象为办公建筑侧储能');
text(s,'项目背景',58,187,245,38,24,C.blue,true);
text(s,'面向办公楼能源管理，通过储能充放电降低取电高峰',58,232,1155,50,31,C.ink,true);
table(s,[['行业痛点','对储能削峰的影响'],['储能资源有限','电池容量与功率受限，需要把电量留给高峰'],['负荷高峰难预测','提前放电或误充电，可能错过高峰甚至形成新峰'],['预测评价与应用目标不一致','平均误差更低，不代表调度后的实际峰值更低']],58,310,1164,240,[370,794],{size:25});
text(s,'项目目标：选择更适合储能调度的预测组合，降低实际取电峰值',58,583,1160,53,27,C.blue,true);
note(s,'先从用能管理问题开场。电池容量有限，若预测高峰过早，电池可能提前用完，也可能因充电时机错误形成新峰。本页解释工程机制，不将其当作已发生的现场案例或量化经济收益。建议 40 秒。',['reports/provincial_20261012/technical_report.md §1','src/battery/optimizer.py','docs/ENGINEERING_INTEGRATION.md']);
// 3. Research question and definitions combined.
s=slide(titles[2],'','');
text(s,'MAE / RMSE 汇总全天误差，不区分误差发生时的调度价值。',58,184,1164,51,27,C.ink,true);
text(s,'削峰取决于高峰时刻、可用电量和充放电安排；\n低谷误差也可能通过充电与 SOC 影响后续高峰。',58,244,1164,74,26,C.muted);
table(s,[['测试集对照','归一化 RMSE ↓','归一化后悔值 ↓'],['LightGBM','0.2169','0.1161'],['XGBoost','0.2168','0.1175']],58,344,1164,174,[470,347,347],{size:25});
text(s,'验证集同样观察到：预测最优与决策最优权重并不总相同',58,540,1164,42,27,C.blue,true);
text(s,'日后悔值 = 实际日峰值 − 同约束下 Oracle 理想日峰值（kW）\nOracle 已知全日实际负荷，仅作事后理想参照',58,591,1160,67,24,C.muted);
note(s,'6/8 来自验证集同一权重网格的不同选择目标，不是测试集上的胜负数。下方测试反例中 XGBoost 的 RMSE 略好，但后悔值略差，差距很小，只证明两类排序不等价。Oracle 事后知道实际负荷，仅用于比较，不可部署。建议 40 秒。',['outputs/phase8/selected_weights.csv','outputs/phase9/final_benchmark.csv','outputs/phase9_1/metric_semantics.json']);
// 4. Innovation and prior-work distinction.
s=slide(titles[3],'创新点','定位：面向建筑储能的应用方法改进；已有任务导向预测研究是本工作的基础');
text(s,'方法创新｜改变融合权重的选择目标',58,185,1164,49,30,C.blue,true);
text(s,'用验证集储能调度后悔值代替预测误差，\n选择 DayWeek 与 LightGBM 的融合权重。',58,245,1164,93,32,C.ink,true);
table(s,[['工程贡献','已完成的工作'],['逐建筑适配','每栋楼独立验证选权，测试期保持固定'],['公平仿真评测','各方法使用相同的电池约束与优化器'],['离线系统原型','回放多建筑调度结果，核对配置与方法差异']],58,372,1164,226,[310,854],{size:25});
text(s,'创新定位：决策导向思想在建筑储能削峰中的应用方法改进',58,607,1164,31,23,C.muted);
note(s,'已有工作已经研究任务导向预测和决策导向组合，不能声称首次提出该思想。本项目的具体改进是：用验证集上固定储能优化器的实际后悔值，选择 DayWeek-LightGBM 的有限网格凸组合。创新属于应用方法适配，不是新型 LightGBM、端到端学习或新优化理论。评测与系统是支撑贡献。建议 45 秒。',['src/phase8.py select_forecast_weight / select_decision_weight','reports/provincial_20261012/technical_report.md §4.1','Stratigakos et al. (2025), Decision-focused linear pooling for probabilistic forecast combination. DOI: 10.1016/j.ijforecast.2024.11.006','https://portaldelainvestigacion.uma.es/documentos/675f922a60134444f312094d']);
// 5. Single method slide.
s=slide(titles[4],'核心方法','候选权重 w = 0.0、0.1、…、1.0；预测器与优化器分别运行');
text(s,'DOEF = w × LightGBM + (1 − w) × DayWeek',58,197,1164,80,37,C.blue,true,'center');
text(s,'LightGBM：拟合非线性变化      DayWeek：前日与前周同小时负荷的均值',58,290,1164,49,25,C.muted,false,'center');
table(s,[['阶段','操作','输出'],['训练','历史负荷与日历特征拟合预测器','固定预测分量'],['验证','11 组权重进入相同电池优化器，比较后悔值','每栋楼一个权重 w'],['测试','权重固定后，用实际负荷评价调度计划','预测误差、后悔值、削峰率']],58,379,1164,229,[156,684,324],{size:24,highlightRow:2});
note(s,'用一句话解释 DOEF：我们不改 LightGBM 的训练目标，而是改变预测组合的选择标准。DayWeek 等于目标前 24 小时及 168 小时负荷的平均；w 是 LightGBM 的比例。验证集先生成调度，再用验证期已观测负荷计算后悔值，测试期不重新选择。端点 w=0 和 w=1 分别退化成两个分量，不强制混合。建议 45 秒。',['outputs/phase8/run_config.json','outputs/phase8/selected_weights.csv','src/phase8.py']);
// 6. Experimental setup / metric definitions / timing.
s=slide(titles[5],'实验设计','固定样本多建筑评测；未验证未见建筑迁移，历史测试期已被查看');
text(s,'BDG2 公开数据',58,185,480,47,31,C.ink,true);
text(s,'296 栋办公楼候选 · 82 栋质量合格 · 8 栋固定样本',58,238,1160,42,26,C.blue,true);
table(s,[['阶段（特征时刻）','时间窗口','使用方式'],['训练','2016-01 至 2017-10','拟合与训练期负荷尺度'],['验证','2017-11','选模、选权重，清除跨界标签'],['测试','2017-12','30 个完整目标日，共 5,760 小时']],58,302,1164,224,[300,410,454],{size:24});
text(s,'统一电池条件：容量为训练期平均日用电量的 10%，往返效率 90%',58,550,1164,39,25,C.ink);
text(s,'归一化指标：各楼指标 ÷ 训练期平均负荷，再按建筑等权平均',58,598,1164,32,23,C.muted);
note(s,'原始覆盖 2016—2017 年。按特征时刻切分；逐小时用 t 时刻信息预测 t+24 小时，所以测试目标日为 2017-12-02 至 2017-12-31。训练和验证边界按标签可用性清除。建筑资格筛选使用预定义三个窗口的原始覆盖，代表性抽样仅使用训练期形态，不使用测试成绩。不是全新盲测或跨建筑零样本泛化。每天初始、终止 SOC 都为 50%，统一固定参数。建议 45 秒。',['src/features/load_features.py','src/models/train_lgbm.py','outputs/phase7/selected_buildings.json','outputs/phase7/building_battery_configs.csv','outputs/phase9_1/final_reporting_summary.json']);
// 7. Core result, combined macro result and building-level evidence.
s=slide(titles[6],'核心结果','柱高为逐楼归一化日均后悔值，越低越好；八建筑均展示');
card(s,'归一化 MAE','降低 6.36%',58,370,C.pale,C.blue);
card(s,'归一化后悔值','降低 3.61%',455,370,'#EEE8F7',C.purple);
card(s,'逐建筑后悔值比较','6 胜 · 2 平 · 0 负',852,370,'#EAF0F5',C.ink);
const br=E.bootstrap_rows;
const ch=s.charts.add('bar',{position:{left:58,top:305,width:1164,height:260},categories:br.map(r=>r.building.split('_').at(-1)),series:[{name:'LightGBM',values:br.map(r=>Number((r.mean_daily_regret_lightgbm/r.train_mean_load).toFixed(9))),fill:C.orange},{name:'DOEF',values:br.map(r=>Number((r.mean_daily_regret_doef/r.train_mean_load).toFixed(9))),fill:C.blue}],hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:18}},barOptions:{direction:'column',grouping:'clustered',gapWidth:65},xAxis:{textStyle:{fontSize:16},majorGridlines:null},yAxis:{min:0,max:.30,majorUnit:.10,numberFormatCode:'0.00',textStyle:{fontSize:16},majorGridlines:{fill:C.line,width:1}},chartFill:C.light,plotAreaFill:C.light});chartFont(ch);
text(s,'柱高：归一化日均后悔值 ↓；差值 95% 自助法区间［−0.006850，−0.001719］',58,579,1160,34,21,C.muted);
text(s,'区间不跨 0，支持本样本中后悔值降低；跨月份稳定性仍需检验',58,619,1160,34,23,C.blue,true);
note(s,'改进率来自未舍入的跨楼等权归一化均值。6胜2平0负比较对象为 LightGBM，平局来自两栋楼 w=1。图示按已冻结建筑顺序。95%区间来自原 Phase9.1 建筑级重采样，8个建筑单位、10000次、种子42，本次未更新这个区间。结论只适用于这组样本，不能把3.61%说成电费、能耗或总峰值的降幅。建议 50 秒。',['outputs/phase9_1/final_reporting_summary.json','outputs/phase9_1/building_level_bootstrap.csv']);
// 8. Existing ablations, made visible and editable.
s=slide(titles[7],'机制验证','同一批预测分量、同一电池优化器、同一测试期；从既有结果整理，无新增训练');
const names=['仅 DayWeek（w=0）','仅 LightGBM（w=1）','等权融合（w=0.5）','逐楼按 MAE 选权重','全楼共用决策权重（w=0.8）','DOEF：逐楼按后悔值选权重'];
table(s,[['方法','归一化 MAE ↓','归一化后悔值 ↓'],...E.ablation.map((r,i)=>[names[i],num(r.mae,4),num(r.regret,4)])],58,185,1164,315,[618,273,273],{size:23,highlightRow:6});
text(s,'对比逐楼 MAE 选权：后悔值降低 12.48%（5 胜 / 2 平 / 1 负）',58,512,1164,40,25,C.blue,true);
text(s,'对比全楼共用决策权重：逐楼选权进一步降低后悔值 3.17%',58,556,1164,40,25,C.ink,true);
text(s,'去掉 Gerardo 后仍降低 3.41%；逐一移除各楼的范围为 3.41%～14.22%\n固定模型与权重的留一建筑汇总；收益幅度具有样本依赖性',58,607,1164,49,21,C.muted);
note(s,'这是证明方法贡献最直接的对照。逐楼 MAE vs 逐楼后悔值只改变选择规则，两个分量和优化器不变；改善12.4781%，5胜2平1负。全局决策权重对照可检查逐建筑权重作用，DOEF相对它改善3.1677%。等权行直接复用 ForecastSelectedGlobal，因为当时选中的全局 MAE 权重恰为0.5，这是数值等价对照，不伪称新预注册实验。12.48%的约82.44%归一化差额由Gerardo贡献，因此同时展示留一楼汇总范围，不能用它代替相对LightGBM的3.61%。此处留一分析仅重新汇总既有结果，没有删楼重训或改选样本。建议 55 秒。',['outputs/phase8/global_test_summary.csv','outputs/phase8/global_selected_weights.json','outputs/phase8/test_decision_metrics.csv','outputs/phase7/building_battery_configs.csv','reports/provincial_20261012/evidence.json']);
// 9. Correct the historically misleading case description.
s=slide(titles[8],'失效分析','Joey，2017-12-14；按两种选权策略的测试日峰差异最大事后选取');
text(s,'整段削峰率：平均 6.44% · 最小 −1.02%',58,180,1160,56,36,C.blue,true);
const caseRows=E.case.rows;
const getCase=m=>caseRows.find(r=>r.method===m);
table(s,[['同一天的调度方式','实际日峰值（kW）'],['无储能',num(getCase('Oracle').original_peak,2)],['按 MAE 选权重',num(getCase('ForecastSelectedPerBuilding').realized_peak,2)],['DOEF',num(getCase('DecisionSelectedPerBuilding').realized_peak,2)],['Oracle（事后理想参照）',num(getCase('Oracle').realized_peak,2)]],58,256,770,235,[470,300],{size:24,highlightRow:3});
text(s,'这一天',871,261,350,43,29,C.orange,true);
text(s,'DOEF 比 MAE 选权重\n高出 47.54 kW\n\n平均改善不保证逐日最优',871,317,351,158,24,C.ink);
text(s,'Joey · 2017-12-14：两策略日峰差最大的测试日（事后选取）',58,529,1164,43,25,C.ink,true);
text(s,'适用范围：固定 8 栋建筑、一个测试月与既定电池配置',58,588,1164,38,25,C.blue,true);
text(s,'削峰率 =（无储能整段峰值 − 调度后整段峰值）/ 无储能整段峰值 × 100%',58,630,1164,30,22,C.muted);
note(s,'本页纠正原PPT第19页的案例说明。src/phase8.py 使用两策略测试日峰差绝对值的最大项选择案例，不是测试前预先选定。该日DOEF的1380.125054 kW高于预测选权重的1332.581714 kW；二者都低于无储能1446.768 kW。该日失利与Joey整月最小削峰率-1.017%是不同统计事实，不能把整月负值归因于这个案例日。旧图彩色线为realized_grid_load，并非负荷预测。本版用可编辑表清晰呈现已保存日峰数值，不推断没有被曲线证明的具体充电因果。建议 40 秒。',['src/phase8.py _plots','outputs/phase8/test_daily_decision_metrics.csv','outputs/phase8/test_decision_metrics.csv','outputs/phase9/final_benchmark.csv']);
// 10. Actual UI.
s=slide(titles[9],'系统展示','现有程序的真实界面；读取已保存实验结果，不接收设备控制指令');
await pic(s,'reports/provincial_20261012/assets/system_demo.png',58,205,854,365,{left:0.02,top:0.28,right:0.02,bottom:0.20});
text(s,'已实现',950,191,270,46,29,C.blue,true);
text(s,'八建筑自动巡演\n\n电池配置与结果核对\n\n多方法削峰比较\n\n本地或便携 HTML 回放',950,265,265,295,25,C.ink);
text(s,'系统定位：离线仿真验证工具，用于多建筑调度结果回放与核对',58,609,1164,44,25,C.blue,true);
note(s,'展示界面来自项目现有GUI截图。演示顺序为八建筑巡演、查看运行与电池参数、综合结果。GUI曲线是每日最大取电功率，不是逐小时充放电功率。预测和优化在离线实验程序完成；GUI回放已保存结果，不现场重训、不实时优化、不下发指令。建议40秒；如播放视频，应提前确认现场时长。',['reports/provincial_20261012/assets/system_demo.png','gui/README.md','gui/server.py','docs/ENGINEERING_INTEGRATION.md']);
// 11. Application value and explicit scope.
s=slide(titles[10],'应用价值','当前成果用于离线方案比较；仿真指标不等同现场实测收益');
text(s,'已完成：从预测组合、约束调度到结果展示的离线验证流程',58,184,1164,48,29,C.blue,true);
table(s,[['可支持的工作','已有成果提供的依据'],['预测方法比较','统一数据切分与电池约束，同时比较误差和调度效果'],['逐建筑方案评估','展示各楼融合权重、后悔值与削峰率，保留失效案例'],['实验复核与演示','保存预测及调度输出，通过 GUI 核对配置与结果']],58,275,1164,264,[340,824],{size:25});
text(s,'应用价值：让预测方法的选择有削峰结果可依据、有实验过程可核对',58,565,1164,48,27,C.ink,true);
text(s,'结果口径：建筑储能离线仿真，不直接换算为现场电费、能耗或碳减排收益',58,620,1164,34,22,C.muted);
note(s,'这一页只介绍已经完成的工作如何支持离线方案比较。项目保存了预测、权重、电池配置与调度结果，并通过GUI回放和核对；统一约束允许评委比较不同预测方法的实际调度效果。逐楼结果和失效案例帮助理解平均改善的适用范围。当前没有现场运行或电费、碳收益的实测结论。建议40秒。',['docs/ENGINEERING_INTEGRATION.md','reports/provincial_20261012/technical_report.md §4–5','outputs/phase8/test_decision_metrics.csv','gui/README.md']);
// 12. Conclusions without an empty thanks slide.
s=slide(titles[11],'结论','智储云控 · DOEF · 8 栋办公建筑离线仿真',true);
text(s,'核心方法',58,187,180,43,27,C.cyan,true);
text(s,'用验证集调度后悔值，逐楼选择\nLightGBM 与 DayWeek 的融合权重',267,179,950,76,29,C.white,true);
line(s,58,272,1160,'#244054');
text(s,'核心结果',58,296,180,43,27,C.cyan,true);
text(s,'相对 LightGBM：归一化 MAE −6.36%，后悔值 −3.61%\n6 胜 2 平；差值区间不跨 0；仿真平均削峰 6.44%，存在失效',267,289,950,87,26,C.white,true);
line(s,58,391,1160,'#244054');
text(s,'适用边界',58,414,180,43,27,C.cyan,true);
text(s,'BDG2 固定 8 栋办公楼 · 测试月 2017-12\n电池容量为训练期平均日用电量的 10%，往返效率 90%',267,407,950,79,26,C.white);
line(s,58,500,1160,'#244054');
text(s,'后续验证',58,526,180,43,27,C.cyan,true);
text(s,'跨月份验证：检查不同月份的效果稳定性\n电池参数敏感性：比较不同容量与功率设置',267,521,950,88,27,C.white,true);
note(s,'我们完成了一个可运行的离线预测调度流程。贡献是把预测组合的选择标准直接连到储能削峰效果；固定实验支持平均改善，也保留失效案例。展望只保留两项：跨月份验证与电池参数敏感性，均未计入本次已完成实验。感谢评委老师。建议20秒。全套12页主讲按上述建议约8分钟；根据现场时长调整。',['outputs/phase9_1/final_reporting_summary.json','docs/ENGINEERING_INTEGRATION.md']);
await fs.writeFile(path.join(HERE,'speaker_notes.json'),JSON.stringify(notes,null,2)+'\n');
const candidatePath=path.join(BUILD,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidatePath);
await fs.mkdir(path.join(BUILD,'final'),{recursive:true});
const finalPath=path.join(BUILD,'final/validated.pptx');
const result=await finalizePresentation({workspaceDir:ROOT,candidatePath,finalPath,pythonExecutable:RUNTIME+'/python/python.exe',integrityValidatorPath:SKILL+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:SKILL+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...[2,3,4,5,6,8,9,11].flatMap(n=>['--require-native-table-slide',String(n)])],explicitTotalSlideCount:12,requiredNativeTableOwnerSlides:[2,3,4,5,6,8,9,11],requiredNativeChartOwnerSlides:[7],materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'reference',families:[FONT],referencePath:path.join(ROOT,'outputs/provincial_20261012/DOEF_Provincial_Submission.pptx'),referenceSha256:(await import('node:crypto')).createHash('sha256').update(await fs.readFile(path.join(ROOT,'outputs/provincial_20261012/DOEF_Provincial_Submission.pptx'))).digest('hex')},verifyArtifactToolImport:true,receiptPath:path.join(BUILD,'validation.json')});
await fs.writeFile(path.join(HERE,'build_receipt.json'),JSON.stringify({status:'candidate_pending_visual_review',build_dir:BUILD,final_path:finalPath,slide_count:12,validation_receipt:path.join(BUILD,'validation.json')},null,2)+'\n');
await fs.copyFile(finalPath,path.join(OUT,'DOEF_Provincial_Submission.pptx'));
console.log(JSON.stringify({finalPath,BUILD,slideCount:p.slides.items.length,package:result.packageIntegrity,layout:result.presentationLayout},null,2));
