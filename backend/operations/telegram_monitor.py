import asyncio,json,os,socket,ssl,time,urllib.parse,urllib.request
from pathlib import Path
from backend.db.engine import SessionLocal
from backend.db.models import MonitoringSettings
from backend.monitoring_crypto import decrypt_secret
from backend.node.health import build_nodes_health
STATE=Path('/var/lib/ov-panel/monitor-state.json')
def send(t,c,m):
 d=urllib.parse.urlencode({'chat_id':c,'text':m}).encode(); urllib.request.urlopen(urllib.request.Request(f'https://api.telegram.org/bot{t}/sendMessage',data=d,method='POST'),timeout=15).read()

# Public helper shared by the scheduled user notifier.
send_telegram = send
def ssl_days(h,p):
 ctx=ssl.create_default_context()
 with socket.create_connection((h,p),timeout=10) as s:
  with ctx.wrap_socket(s,server_hostname=h) as x: exp=ssl.cert_time_to_seconds(x.getpeercert()['notAfter'])
 return int((exp-time.time())/86400)
async def main():
 db=SessionLocal()
 try:
  cfg=db.query(MonitoringSettings).filter(MonitoringSettings.id==1).first()
  if not cfg or not cfg.enabled:return
  token=decrypt_secret(cfg.telegram_token_encrypted); chat=cfg.telegram_chat_id
  if not token or not chat:return
  nodes=await build_nodes_health(db); cpu=cfg.cpu_limit; ram=cfg.ram_limit; disk=cfg.disk_limit; host=cfg.ssl_host; port=cfg.ssl_port; days=cfg.ssl_warning_days
 finally: db.close()
 alerts={}; st=os.statvfs('/'); used=round(100*(1-st.f_bavail/st.f_blocks),1)
 if used>=disk:alerts['panel:disk']=f'⚠️ PVNetwork Panel disk usage: {used}%'
 for n in nodes:
  i=n.get('id'); name=n.get('name') or f'Node {i}'; reasons=n.get('health_reason') or []
  if n.get('health')=='offline':alerts[f'n:{i}:down']=f'🔴 Node DOWN: {name}'
  if n.get('cpu_usage') is not None and float(n['cpu_usage'])>=cpu:alerts[f'n:{i}:cpu']=f'⚠️ High CPU: {name} — {float(n["cpu_usage"]):.1f}%'
  if n.get('memory_usage') is not None and float(n['memory_usage'])>=ram:alerts[f'n:{i}:ram']=f'⚠️ High RAM: {name} — {float(n["memory_usage"]):.1f}%'
  if 'node_api_unreachable' in reasons:alerts[f'n:{i}:sync']=f'🔴 Sync unavailable: {name}'
 if host:
  try:
   left=ssl_days(host,port)
   if left<=days:alerts['ssl']=f'⚠️ SSL for {host} expires in {left} day(s)'
  except Exception as e:alerts['ssl']=f'🔴 SSL check failed for {host}: {type(e).__name__}'
 try: old=json.loads(STATE.read_text()).get('alerts',{})
 except Exception: old={}
 for k,v in alerts.items():
  if old.get(k)!=v:send(token,chat,v)
 for k,v in old.items():
  if k not in alerts:send(token,chat,'✅ Resolved: '+v)
 tmp=STATE.with_suffix('.tmp'); tmp.write_text(json.dumps({'checked_at':int(time.time()),'alerts':alerts},ensure_ascii=False)); tmp.replace(STATE)
if __name__=='__main__':asyncio.run(main())
