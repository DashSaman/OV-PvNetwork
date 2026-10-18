// Read actual rendered backgrounds without changing geometry or backgrounds.
export async function renderedText(page) {
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const elements=await page.evaluate(()=>{
  const results=[],seen=new Set(),walk=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  const parse=s=>(s.match(/[\d.]+/g)||[]).map(Number);
  const add=(el,rects,text,kind='text')=>{
   if(!el||el.closest('[inert],script,style,[aria-hidden="true"],:disabled')||/^[\p{Extended_Pictographic}\uFE0F\s]+$/u.test(text))return;
   const s=getComputedStyle(el);if(s.visibility!=='visible'||s.display==='none'||!rects.length)return;
   let opacity=1;for(let p=el;p;p=p.parentElement)opacity*=Number(getComputedStyle(p).opacity);
   const ink=kind==='placeholder'?getComputedStyle(el,'::placeholder').color:el instanceof SVGElement?s.fill:s.webkitTextFillColor||s.color;
   const manual=kind==='file'||ink.includes('url(')||ink==='none'||s.backgroundClip==='text'||s.webkitBackgroundClip==='text';
   const color=parse(ink),alpha=(color[3]??1)*opacity;
   if(!alpha&&!manual)return;
   const points=[];
   for(const box of rects)for(const fy of [.25,.5,.75])for(const fx of [.1,.3,.5,.7,.9]){
    const x=box.x+box.width*fx,y=box.y+box.height*fy;
    if(x<0||y<0||x>=innerWidth||y>=innerHeight)continue;
    const top=document.elementFromPoint(x,y);if(top&&(el.contains(top)||top===el))points.push({x:Math.floor(x),y:Math.floor(y)});
   }
   if(!points.length)return;
   if(!seen.has(el)){el.dataset.pvPixelText=String(seen.size);seen.add(el);}
   results.push({id:el.dataset.pvPixelText,selector:el.id?'#'+el.id:el.tagName.toLowerCase()+'.'+[...el.classList].join('.'),kind,text:text.trim().slice(0,90),color,alpha,minimum:parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.666&&Number(s.fontWeight)>=700)?3:4.5,manual,points});
  };
  let node;while((node=walk.nextNode()))if(node.textContent.trim()){
   const range=document.createRange();range.selectNodeContents(node);add(node.parentElement,[...range.getClientRects()],node.textContent);
  }
  for(const el of document.querySelectorAll('input:not([type=checkbox]):not([type=radio]),textarea,select')){
   const rect=el.getBoundingClientRect(),s=getComputedStyle(el),pad=parseFloat(s.paddingLeft)||4;
   const text=el.type==='file'?'Native file selector':el.value||el.placeholder||'';
   if(text)add(el,[{x:rect.x+pad,y:rect.y+4,width:Math.max(0,rect.width-pad-25),height:rect.height-8}],text,el.type==='file'?'file':el.value?'value':'placeholder');
  }
  return results;
 });
 const sheet=await page.addStyleTag({content:'[data-pv-pixel-text], [data-pv-pixel-text] * {color:transparent!important;-webkit-text-fill-color:transparent!important;text-shadow:none!important;} [data-pv-pixel-text]::placeholder {color:transparent!important;opacity:0!important;} svg [data-pv-pixel-text] {fill:transparent!important;stroke:transparent!important;}'});
 let png;try{png=(await page.screenshot({scale:'css',animations:'disabled'})).toString('base64');}finally{await sheet.evaluate(el=>el.remove());}
 const measured=await page.evaluate(async({png,elements})=>{
  const img=new Image();img.src='data:image/png;base64,'+png;await img.decode();const canvas=document.createElement('canvas');canvas.width=img.width;canvas.height=img.height;const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(img,0,0);
  const lum=rgb=>rgb.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
  return elements.map(({points,...el})=>{
   if(el.manual)return {...el,reason:el.kind==='file'?'UA file-selector text is not an ordinary DOM value; authored opaque color pairs checked separately, native painting remains manual':'Text-clipped gradient/image; explicit visual review'};
   let ratio=Infinity,worst;for(const {x,y} of points){const bg=[...ctx.getImageData(x,y,1,1).data].slice(0,3),ink=el.color.slice(0,3).map((c,i)=>c*el.alpha+bg[i]*(1-el.alpha)),a=lum(bg),b=lum(ink),r=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);if(r<ratio){ratio=r;worst={x,y,background:bg};}}
   return {...el,ratio,...worst};
  });
 },{png,elements});
 await page.evaluate(()=>document.querySelectorAll('[data-pv-pixel-text]').forEach(el=>delete el.dataset.pvPixelText));
 return measured;
}

// Native file-button/name strings live in UA shadow UI. Do not mistake an empty
// value or the native button's ink for a rasterized textbox background. Explicit
// opaque author colors permit separate checks without claiming OS certification.
export async function fileControlColors(page) {
 return page.locator('input[type=file]').evaluateAll(els=>{
  const rgba=value=>(value.match(/[\d.]+/g)||[]).map(Number);
  const lum=rgb=>rgb.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
  return els.filter(el=>el.getClientRects().length&&!el.disabled).map(el=>{
   const input=getComputedStyle(el),button=getComputedStyle(el,'::file-selector-button');
   let opacity=1;for(let p=el;p;p=p.parentElement)opacity*=Number(getComputedStyle(p).opacity);
   const pairs=[['filename',input],['button',button]].map(([part,s])=>{
    const fg=rgba(s.color),bg=rgba(s.backgroundColor),opaque=fg.length>=3&&bg.length>=3&&(fg[3]??1)===1&&(bg[3]??1)===1&&opacity===1;
    const a=lum(fg),b=lum(bg);return {part,color:s.color,background:s.backgroundColor,opaque,ratio:opaque?(Math.max(a,b)+.05)/(Math.min(a,b)+.05):null};
   });return {id:el.id||el.className,pairs};
  });
 });
}

// Conservative bounds for an opaque text-clipped gradient: rasterize its full
// fill and actual backdrop separately, then compare the worst luminance ranges.
// This excludes text shadows and refuses alpha/hidden/occluded test subjects.
export async function renderedGradientText(page,selector) {
 const el=page.locator(selector);if(await el.count()!==1)throw Error('One gradient subject required');
 await el.evaluate(node=>{node.dataset.pvGradient='true';const s=getComputedStyle(node);if(!s.backgroundImage.startsWith('linear-gradient(')||s.backgroundImage.includes('rgba('))throw Error('Opaque linear gradient required');for(let p=node;p;p=p.parentElement)if(Number(getComputedStyle(p).opacity)!==1)throw Error('Opaque gradient ancestry required');});
 const points=await el.evaluate(node=>{const r=node.getBoundingClientRect(),points=[];for(let y=Math.max(3,Math.ceil(r.top)+3);y<Math.min(innerHeight-3,r.bottom-3);y+=2)for(let x=Math.max(3,Math.ceil(r.left)+3);x<Math.min(innerWidth-3,r.right-3);x+=2)if(document.elementFromPoint(x,y)===node)points.push({x,y});if(!points.length)throw Error('Visible gradient pixels required');return points;});
 const common='[data-pv-gradient] { -webkit-text-fill-color:transparent!important;color:transparent!important;text-shadow:none!important;filter:none!important; }';
 const backdrop=await page.addStyleTag({content:common+'[data-pv-gradient] { background-image:none!important; }'});
 let bg,fg;try{bg=(await page.screenshot({scale:'css',animations:'disabled'})).toString('base64');}finally{await backdrop.evaluate(n=>n.remove());}
 const foreground=await page.addStyleTag({content:common+'[data-pv-gradient] {background-clip:border-box!important;-webkit-background-clip:border-box!important;border-radius:0!important;}'});
 try{fg=(await page.screenshot({scale:'css',animations:'disabled'})).toString('base64');}finally{await foreground.evaluate(n=>n.remove());await el.evaluate(n=>delete n.dataset.pvGradient);}
 return page.evaluate(async({bg,fg,points})=>{
  const lum=rgb=>rgb.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
  const range=async png=>{const img=new Image();img.src='data:image/png;base64,'+png;await img.decode();const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(img,0,0);const values=points.map(({x,y})=>lum([...ctx.getImageData(x,y,1,1).data]));return {min:Math.min(...values),max:Math.max(...values)};};
  const background=await range(bg),foreground=await range(fg);return {pixels:points.length,background,foreground,ratio:foreground.min>background.max?(foreground.min+.05)/(background.max+.05):background.min>foreground.max?(background.min+.05)/(foreground.max+.05):1,method:'Conservative independent raster luminance ranges; no text shadow credit'};
 },{bg,fg,points});
}

export async function controlEdges(page,selector) {
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const values=await page.locator(selector).evaluateAll(els=>els.filter(el=>{const r=el.getBoundingClientRect();return el.getClientRects().length&&!el.closest(':disabled')&&document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===el;}).map(el=>{
  const s=getComputedStyle(el),r=el.getBoundingClientRect();return {name:el.name||el.getAttribute('aria-label')||el.textContent.slice(0,60),tag:el.tagName,border:s.borderTopWidth==='0px'||s.borderTopStyle==='none'?null:s.borderTopColor,outline:s.outlineColor,background:s.backgroundColor,points:[{x:r.x+r.width/2,y:r.y-1},{x:r.x+r.width/2,y:r.bottom+1}],rect:{x:r.x,y:r.y,width:r.width,height:r.height}};
 }));
 const png=(await page.screenshot({scale:'css',animations:'disabled'})).toString('base64');
 return page.evaluate(async({png,values})=>{
  const img=new Image();img.src='data:image/png;base64,'+png;await img.decode();const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(img,0,0);
  const lum=rgb=>rgb.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
  return values.map(v=>{const parse=s=>(s?.match(/[\d.]+/g)||[]).map(Number),border=parse(v.border),fill=parse(v.background),rs=v.points.filter(p=>p.x>=0&&p.y>=0&&p.x<c.width&&p.y<c.height).map(p=>{
   const bg=[...ctx.getImageData(Math.floor(p.x),Math.floor(p.y),1,1).data].slice(0,3),a=lum(bg);
   const contrast=ink=>{if(ink.length<3)return 0;const alpha=ink[3]??1,b=lum(ink.slice(0,3).map((v,i)=>v*alpha+bg[i]*(1-alpha)));return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);};
   const borderRatio=contrast(border),fillRatio=contrast(fill);
   // A contrasting fill also identifies a field; a border is not mandatory.
   return {background:bg,borderRatio,fillRatio,ratio:Math.max(borderRatio,fillRatio)};
  });return {...v,measurements:rs,ratio:rs.length?Math.min(...rs.map(r=>r.ratio)):null};});
 },{png,values});
}

export async function renderedFocus(page) {
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const value=await page.evaluate(()=>{const el=document.activeElement,s=getComputedStyle(el),r=el.getBoundingClientRect(),w=parseFloat(s.outlineWidth),o=parseFloat(s.outlineOffset);return {selector:el.tagName+'.'+el.className,outline:s.outline,color:s.outlineColor,width:w,visible:s.outlineStyle!=='none'&&w>0,points:[{x:r.x-o-w-1,y:r.y+r.height/2},{x:r.right+o+w+1,y:r.y+r.height/2},{x:r.x+r.width/2,y:r.y-o-w-1},{x:r.x+r.width/2,y:r.bottom+o+w+1}]};});
 const png=(await page.screenshot({scale:'css',animations:'disabled'})).toString('base64');
 return page.evaluate(async({png,value})=>{const img=new Image();img.src='data:image/png;base64,'+png;await img.decode();const canvas=document.createElement('canvas');canvas.width=img.width;canvas.height=img.height;const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(img,0,0);const lum=rgb=>rgb.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0),ink=(value.color.match(/[\d.]+/g)||[]).map(Number),measurements=value.points.filter(p=>p.x>=0&&p.y>=0&&p.x<canvas.width&&p.y<canvas.height).map(p=>{const bg=[...ctx.getImageData(Math.floor(p.x),Math.floor(p.y),1,1).data].slice(0,3),a=lum(bg),b=lum(ink);return {background:bg,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};});return {...value,measurements,ratio:measurements.length?Math.min(...measurements.map(x=>x.ratio)):0};},{png,value});
}
