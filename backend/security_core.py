import base64,hashlib,hmac,json,struct,time
from backend.monitoring_crypto import encrypt_secret,decrypt_secret
def new_totp_secret():return base64.b32encode(__import__('secrets').token_bytes(20)).decode().rstrip('=')
def totp(secret,at=None):
 at=int(at or time.time())//30;s=secret.upper()+'='*((8-len(secret)%8)%8);key=base64.b32decode(s);d=hmac.new(key,struct.pack('>Q',at),hashlib.sha1).digest();o=d[-1]&15;return str((struct.unpack('>I',d[o:o+4])[0]&0x7fffffff)%1000000).zfill(6)
def verify_totp(secret,code):return any(hmac.compare_digest(totp(secret,time.time()+x*30),str(code).zfill(6)) for x in (-1,0,1))
def enc(v):return encrypt_secret(v)
def dec(v):return decrypt_secret(v)
