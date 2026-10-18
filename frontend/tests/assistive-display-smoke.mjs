// Browser emulation/AX evidence only, not a real screen reader or OS session.
import {writeFile} from 'node:fs/promises';
import {zoomBrowser} from './browser-zoom.mjs';
import {renderedFocus} from './rendered-contrast.mjs';
import {baseUrl,responseFor,demoToken,routes} from './accessibility-fixtures.mjs';
const browser=await zoomBrowser(),results=[],failures=[];
const check=(value,message)=>{if(!value)throw Error(message);};
async function setup(page,language,theme){
 await page.addInitScript(({language,theme,token})=>{localStorage.setItem('pvnetwork_language',language);localStorage.setItem('ov-dashboard-theme',theme);localStorage.setItem('authToken',token);localStorage.setItem('userRole','main_admin');},{language,theme,token:demoToken()});
 await page.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!==new URL(baseUrl).origin)return route.abort();if(u.pathname.startsWith('/api/'))return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(responseFor(u.href))});return route.continue();});
}
try{
 for(const language of ['en','fa'])for(const theme of ['dark','light'])for(const width of [390,1440]){
  const page=await browser.context.newPage();await page.setViewportSize({width,height:1000});await page.emulateMedia({forcedColors:'active',colorScheme:theme});await setup(page,language,theme);
  const label=`${language}/${theme}/${width}/forced-colors`;
  try{
   await page.goto(baseUrl+'/nodes',{waitUntil:'networkidle'});
   await page.locator('.actions-dropdown-trigger').first().click();await page.getByRole('menuitem',{name:/Node backup.*restore|بکاپ.*بازیابی نود/i}).click();await page.locator('dialog').waitFor();
   check(await page.evaluate(()=>matchMedia('(forced-colors:active)').matches),'Forced colors not applied');
   const buttons=await page.locator('dialog button').evaluateAll(els=>els.map(el=>{const s=getComputedStyle(el);return {text:el.textContent,border:s.borderTopWidth,style:s.borderTopStyle,adjust:s.forcedColorAdjust};}));
   check(buttons.every(b=>parseFloat(b.border)>=1&&b.style==='solid'&&b.adjust==='auto'),'Forced-color button boundary missing/UA adjustment disabled');
   await page.keyboard.press('Tab');const focus=await renderedFocus(page);check(focus.visible&&focus.ratio>=3,'Forced-color focus missing/low contrast');
   const protocol=await page.context().newCDPSession(page),tree=await protocol.send('Accessibility.getFullAXTree');await protocol.detach();
   const ax=tree.nodes.filter(n=>!n.ignored).map(n=>({role:n.role?.value,name:n.name?.value}));
   check(ax.some(n=>n.role==='dialog'&&n.name)&&ax.some(n=>n.role==='textbox'&&/SSH/.test(n.name)),'Named modal/fields absent from actual browser AX tree');
   check(!ax.some(n=>n.role==='link'&&['Dashboard','داشبورد'].includes(n.name)),'Background navigation still exposed in browser AX tree during native modality');
   await page.keyboard.press('Escape');await page.locator('dialog').waitFor({state:'hidden'});check(await page.locator('.actions-dropdown-trigger').first().evaluate(el=>el===document.activeElement),'Exact invoker did not return');
   let menu=false;if(width===390){const trigger=page.locator('.mobile-more-trigger');await trigger.focus();await page.keyboard.press('Enter');await page.getByRole('menu').waitFor();check(await trigger.getAttribute('aria-controls')==='mobile-more-menu'&&await page.locator('#mobile-more-menu:visible').count()===1,'Expanded ID reference invalid');const items=page.getByRole('menuitem');await page.keyboard.press('End');check(await items.last().evaluate(el=>el===document.activeElement),'End did not focus last menu item');await page.keyboard.press('ArrowDown');check(await items.first().evaluate(el=>el===document.activeElement),'Arrow wrapping failed');await page.keyboard.press('Escape');check(await trigger.evaluate(el=>el===document.activeElement),'Escape did not restore More');check(await trigger.getAttribute('aria-expanded')==='false'&&!await trigger.getAttribute('aria-controls'),'Closed menu has stale state');menu=true;}
   results.push({label,buttons,focus,ax,mobileMenu:menu});
  }catch(error){failures.push({label,error:error.message});}finally{await page.close();}
 }
 for(const language of ['en','fa'])for(const theme of ['dark','light']){
  const page=await browser.context.newPage();await page.setViewportSize({width:1280,height:1000});await setup(page,language,theme);
  for(const route of routes){const label=`${language}/${theme}/${route}/native400-text-spacing`;
   try{await page.goto(baseUrl+route,{waitUntil:'networkidle'});check(page.url().replace(/\/$/,'')===(baseUrl+route).replace(/\/$/,''),'Wrong route');await browser.setZoom(page,4);
    await page.addStyleTag({content:'*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}'});
    const layout=await page.evaluate(()=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth,clipped:[...document.querySelectorAll('button,input,select,textarea,a[href]')].filter(el=>{const r=el.getBoundingClientRect();if(!r.width||!r.height||r.bottom<=0||r.top>=innerHeight||getComputedStyle(el).visibility==='hidden')return false;if(r.left>=-1&&r.right<=innerWidth+1)return false;for(let p=el.parentElement;p;p=p.parentElement){const s=getComputedStyle(p);if(/auto|scroll/.test(s.overflowX)&&p.scrollWidth>p.clientWidth)return false;}return true;}).map(el=>({name:el.getAttribute('aria-label')||el.textContent.slice(0,70),rect:el.getBoundingClientRect().toJSON()}))}));
    check(layout.width<=321&&layout.width>=319,'Native400% did not produce320CSSpx');check(layout.documentWidth<=layout.width+1,'Document requires horizontal scrolling');check(!layout.clipped.length,'Required controls clipped outside a scrollable region: '+JSON.stringify(layout.clipped));results.push({label,...layout});
   }catch(error){failures.push({label,error:error.message});}
  }await page.close();
 }
}finally{await browser.close();}
const summary={forcedColorCases:results.filter(x=>x.buttons).length,native400TextSpacing:results.filter(x=>x.width).length,failures:failures.length,firstFailures:failures.slice(0,6)};
if(process.env.PV_ASSISTIVE_REPORT)await writeFile(process.env.PV_ASSISTIVE_REPORT,JSON.stringify({summary,results,failures},null,2));
console.log('ASSISTIVE_DISPLAY='+JSON.stringify(summary));if(failures.length)process.exitCode=1;
