import hashlib,time
from datetime import date
from backend.db.engine import SessionLocal
from backend.db.models import User,MonitoringSettings,NotificationState
from backend.monitoring_crypto import decrypt_secret
from backend.operations.telegram_monitor import send_telegram
def main():
 db=SessionLocal()
 try:
  c=db.query(MonitoringSettings).filter_by(id=1).first()
  if not c or not c.enabled:return
  token=decrypt_secret(c.telegram_token_encrypted);chat=c.telegram_chat_id
  if not token or not chat:return
  today=date.today()
  for u in db.query(User).filter(User.is_active.is_(True)).all():
   messages=[]
   if u.total and u.total>0 and (u.used or 0)/u.total>=.9:messages.append(f'⚠️ حجم کاربر {u.name} به ۹۰٪ رسیده است.')
   if u.expiry_date:
    left=(u.expiry_date-today).days
    if 0<=left<=3:messages.append(f'⚠️ اعتبار کاربر {u.name} تا {left} روز دیگر منقضی می‌شود.')
   for m in messages:
    key=hashlib.sha256(m.encode('utf-8')).hexdigest();state=db.query(NotificationState).filter_by(key=key).first();now=int(time.time())
    if not state or now-state.sent_at>=86400:
     send_telegram(token,chat,m)
     if not state:state=NotificationState(key=key);db.add(state)
     state.last_value=m;state.sent_at=now
  db.commit()
 finally:db.close()
if __name__=='__main__':main()
