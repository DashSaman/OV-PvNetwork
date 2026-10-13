"""PVNetwork Node: authenticated TLS control plane without development reload."""
import uvicorn
from core.config import settings


def main():
    uvicorn.run('core.app:api',host=settings.listen_host,port=settings.service_port,
                ssl_certfile=settings.tls_certfile,ssl_keyfile=settings.tls_keyfile,
                log_level=settings.debug.lower(),access_log=False)


if __name__=='__main__':main()
