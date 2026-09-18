import time
from backend.db.engine import SessionLocal
from backend.db.models import User,UsageHistory
def record_usage_history():
 db=SessionLocal()
 try:
  now=int(time.time())
  for u in db.query(User).all():db.add(UsageHistory(user_uuid=u.uuid,used=int(u.used or 0),total=u.total,sampled_at=now))
  db.commit()
 finally:db.close()
