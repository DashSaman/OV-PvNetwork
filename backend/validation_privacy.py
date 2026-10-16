"""Validation errors identify fields without serializing submitted credentials."""
from fastapi.responses import JSONResponse


def sensitive_values(body):
    values=[];pending=[body];budget=4096
    names={'key','token','secret','credential','private_key','api_key','access_token','refresh_token','authorization','cookie','database_url'}
    while pending and budget:
        current=pending.pop();budget-=1
        if isinstance(current,dict):
            for key,value in current.items():
                name=str(key).casefold().replace('-','_')
                if isinstance(value,str) and value and (name in names or any(part in name for part in ['password','passphrase','private_key','secret','api_key'])):values.append(value)
                elif isinstance(value,(dict,list)):pending.append(value)
        elif isinstance(current,list):pending.extend(current[:budget])
    return values


async def validation_response(request,error):
    values=sensitive_values(error.body)
    details=[]
    for item in error.errors():
        message=str(item.get('msg','Invalid value'))
        for value in values:message=message.replace(value,'[REDACTED]')
        details.append({'loc':list(item.get('loc',())),'type':item.get('type','value_error'),'msg':message})
    return JSONResponse(status_code=422,content={'detail':details},headers={'Cache-Control':'no-store'})
