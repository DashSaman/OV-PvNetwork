import hmac
from fastapi import Header,HTTPException
from core.config import settings


async def check_api_key(key:str|None=Header(None),api_key:str|None=Header(None),
                        native_key:str|None=Header(None,alias='X-PVNetwork-Node-Key')):
    supplied=[x for x in [native_key,key,api_key] if x]
    if not supplied or any(not hmac.compare_digest(x.encode(),settings.api_key.encode()) for x in supplied):
        raise HTTPException(status_code=401,detail='Invalid node API key')
    return supplied[0]
