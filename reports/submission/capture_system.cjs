// Capture the actual offline application; no fabricated interface or data.
const {chromium}=require(process.env.RUNTIME_NODE_MODULES+'/playwright');
const path=require('node:path');
const fs=require('node:fs');
const {pathToFileURL}=require('node:url');
(async()=>{
 const root=path.resolve(__dirname,'../..');
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1120},deviceScaleFactor:1.5,reducedMotion:'reduce'});
  await page.goto(pathToFileURL(path.join(root,'outputs/gui_demo/DOEF_Dynamic_Demo.html')).href);
  await page.locator('#replay-chart svg').waitFor();
  await page.locator('#tour').click();
  await page.waitForTimeout(3000);
  await page.locator('#tour-pause').click();
  fs.mkdirSync(path.join(__dirname,'assets'),{recursive:true});
  await page.screenshot({path:path.join(__dirname,'assets/system_demo.png'),fullPage:true});
  console.log(await page.title());
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
