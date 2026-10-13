"""Ephemeral callback proof tied to the controller issuing the SSH install."""
import hashlib
import hmac
import secrets
import threading
import time

_pending={}
_lock=threading.RLock()


def register(key):
    nonce=secrets.token_urlsafe(24)
    with _lock:
        now=time.monotonic()
        for identity in list(_pending):
            if _pending[identity]<=now:_pending.pop(identity,None)
        if len(_pending)>=256:raise ValueError('too many pending node callback probes')
        _pending[(hashlib.sha256(key.encode()).hexdigest(),nonce)]=now+1200
    return nonce


def matches(key,nonce):
    digest=hashlib.sha256(key.encode()).hexdigest()
    with _lock:
        for (candidate,challenge),expires in _pending.items():
            if expires>time.monotonic() and hmac.compare_digest(candidate,digest) and hmac.compare_digest(challenge.encode(),nonce.encode()):return True
    return False


def discard(key,nonce):
    with _lock:_pending.pop((hashlib.sha256(key.encode()).hexdigest(),nonce),None)
