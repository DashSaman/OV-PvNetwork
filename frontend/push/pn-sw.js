/* PRIVATE NETWORK WEB PUSH SW V6.4.4 */
self.addEventListener("install",()=>self.skipWaiting());
self.addEventListener("activate",e=>e.waitUntil(self.clients.claim()));
self.addEventListener("push",event=>{
  let data={}; try{data=event.data?event.data.json():{}}catch(_){}
  event.waitUntil(self.registration.showNotification(data.title||"Private Network",{
    body:data.body||"برای تمدید یا خرید سرویس به فروشنده خود مراجعه کنید.",
    icon:data.icon||"/sub-clients/private-network.webp",
    badge:data.badge||"/sub-clients/private-network.webp",
    tag:data.tag||("pn-renewal-"+Date.now()), renotify:false, silent:false,
    timestamp:data.timestamp||Date.now(), data:{url:data.url||null}
  }));
});
self.addEventListener("notificationclick",event=>{
  event.notification.close();
  const raw=event.notification&&event.notification.data?event.notification.data.url:null;
  if(!raw)return;
  try{
    const u=new URL(raw,self.location.origin);
    if(u.origin===self.location.origin&&u.pathname.startsWith("/sub/")){
      event.waitUntil(clients.openWindow(u.href));
    }
  }catch(_){}
});
