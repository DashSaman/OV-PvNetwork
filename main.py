import uvicorn
from backend.config import config


def main():
    uvicorn.run(
        "backend.app:api",
        host=str(config.HOST),
        port=config.PORT,
        reload=False,
        ssl_keyfile=config.SSL_KEYFILE,
        ssl_certfile=config.SSL_CERTFILE,
        # OV_GRACEFUL_SHUTDOWN_V1
        timeout_graceful_shutdown=10,
    )


if __name__ == "__main__":
    main()
