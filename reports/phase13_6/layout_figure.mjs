// Render a layout-only SVG derivative with the frozen chart geometry intact.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire('C:/Users/m/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/package.json');
const {chromium}=require('playwright');
const base=path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/,'$1'));
const source=path.resolve(base,'../../outputs/phase13_5/figures_cn/sci_04_validation_weight_selection_cn.svg');
fs.mkdirSync(path.join(base,'assets'),{recursive:true});
let svg=fs.readFileSync(source,'utf8');
if(!svg.includes('<g id="legend_1">')) throw Error('Expected frozen SVG legend missing');
svg=svg.replace('height="648pt"','height="708pt"').replace('viewBox="0 0 1152 648"','viewBox="0 0 1152 708"').replace('<g id="legend_1">','<g id="legend_1" transform="translate(-350 145)">');
fs.writeFileSync(path.join(base,'assets/figure_04_layout.svg'),svg);
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
const page=await browser.newPage({viewport:{width:1200,height:738},deviceScaleFactor:2});
await page.setContent('<html><body style="margin:0;background:white">'+svg.replace('width="1152pt"','width="1200"').replace('height="708pt"','height="737.5"')+'</body></html>');
await page.evaluate(()=>document.fonts.ready);
await page.screenshot({path:path.join(base,'assets/figure_04_layout.png')});
await browser.close();
