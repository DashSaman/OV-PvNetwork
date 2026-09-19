import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
)


# ==========================================================
# PVNETWORK DATABASE FOUNDATION V2
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(
    dotenv_path=ENV_FILE,
    override=False,
)


DEFAULT_SQLITE_PATH = (
    PROJECT_ROOT /
    "data" /
    "pvnetwork-panel.db"
)


DEFAULT_DATABASE_URL = (
    f"sqlite:///{DEFAULT_SQLITE_PATH}"
)


DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or DEFAULT_DATABASE_URL
)


def _build_engine_options(
    database_url: str,
) -> dict:

    url = make_url(database_url)

    common = {
        "pool_pre_ping": True,
    }

    #
    # SQLite compatibility
    #
    if url.get_backend_name() == "sqlite":

        common.update(
            {
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 15,
                },

                # Keep current production tuning.
                "pool_size": 20,
                "max_overflow": 20,
                "pool_timeout": 5,
            }
        )

        return common


    #
    # PostgreSQL / future SQL databases
    #
    common.update(
        {
            "pool_size": 20,
            "max_overflow": 20,
            "pool_timeout": 10,
            "pool_recycle": 1800,
        }
    )

    return common


engin = create_engine(
    DATABASE_URL,
    **_build_engine_options(
        DATABASE_URL
    ),
)


#
# New canonical name.
#
SessionLocal = sessionmaker(
    bind=engin,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


#
# Backward compatibility.
#
# Existing modules import:
#
#     sessionLocal
#
# Do not remove this alias until all legacy
# modules have been migrated.
#
sessionLocal = SessionLocal


Base = declarative_base()


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


@contextmanager
def db_session():
    """
    Transaction-safe DB session for jobs,
    services and future workers.
    """

    db = SessionLocal()

    try:

        yield db

        db.commit()

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()


def database_backend() -> str:

    return make_url(
        DATABASE_URL
    ).get_backend_name()
