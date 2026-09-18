from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
)

from sqlalchemy.orm import Session

from backend.db.pvnetwork_universal_adapter import (
    UniversalAccountReadAdapter,
)


router = APIRouter(
    prefix="/api/v1/pvnetwork-canary/accounts",
    tags=[
        "PVNetwork Universal Account Canary"
    ],
)


def universal_account_session() -> Session:
    """
    Intentionally unwired to Production.

    A later reviewed patch must explicitly
    provide this dependency.
    """

    raise RuntimeError(
        "Universal Account API is not runtime-wired"
    )


def canary_auth(
    x_pvnetwork_canary_token: str | None = Header(
        default=None,
    ),
) -> None:

    expected_hash = os.environ.get(
        "PVNETWORK_ACCOUNT_CANARY_TOKEN_SHA256"
    )

    if not expected_hash:
        raise HTTPException(
            status_code=503,
            detail={
                "code":
                    "canary_disabled",
                "message_key":
                    "account.canary.disabled",
            },
        )

    if not x_pvnetwork_canary_token:
        raise HTTPException(
            status_code=401,
            detail={
                "code":
                    "unauthorized",
                "message_key":
                    "account.canary.unauthorized",
            },
        )

    supplied_hash = hashlib.sha256(
        x_pvnetwork_canary_token.encode(
            "utf-8"
        )
    ).hexdigest()

    if not hmac.compare_digest(
        supplied_hash,
        expected_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail={
                "code":
                    "unauthorized",
                "message_key":
                    "account.canary.unauthorized",
            },
        )


def adapter(
    session: Session = Depends(
        universal_account_session
    ),
) -> UniversalAccountReadAdapter:

    return UniversalAccountReadAdapter(
        session
    )


def require_account(
    account: UniversalAccountReadAdapter,
    user_uuid: str,
) -> None:

    if account.account_exists(
        user_uuid
    ):
        return

    raise HTTPException(
        status_code=404,
        detail={
            "code":
                "account_not_found",
            "message_key":
                "account.read.not_found",
        },
    )


@router.get("/{user_uuid}")
def get_account(
    user_uuid: str,
    _: None = Depends(canary_auth),
    account: UniversalAccountReadAdapter = Depends(adapter),
):

    data = account.account_snapshot(
        user_uuid
    )

    if data is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code":
                    "account_not_found",
                "message_key":
                    "account.read.not_found",
            },
        )

    return {
        "schema": 1,
        "message_key":
            "account.read.success",
        "account": data,
    }


@router.get("/{user_uuid}/devices")
def get_devices(
    user_uuid: str,
    _: None = Depends(canary_auth),
    account: UniversalAccountReadAdapter = Depends(adapter),
):

    require_account(
        account,
        user_uuid,
    )

    return {
        "schema": 1,
        "items":
            account.devices(
                user_uuid
            ),
    }


@router.get("/{user_uuid}/credentials")
def get_credentials(
    user_uuid: str,
    _: None = Depends(canary_auth),
    account: UniversalAccountReadAdapter = Depends(adapter),
):

    require_account(
        account,
        user_uuid,
    )

    return {
        "schema": 1,
        "items":
            account.credential_metadata(
                user_uuid
            ),
    }


@router.get("/{user_uuid}/protocol-entitlements")
def get_protocol_entitlements(
    user_uuid: str,
    _: None = Depends(canary_auth),
    account: UniversalAccountReadAdapter = Depends(adapter),
):

    require_account(
        account,
        user_uuid,
    )

    return {
        "schema": 1,
        "items":
            account.protocol_entitlements(
                user_uuid
            ),
    }


@router.get("/{user_uuid}/preference")
def get_preference(
    user_uuid: str,
    _: None = Depends(canary_auth),
    account: UniversalAccountReadAdapter = Depends(adapter),
):

    require_account(
        account,
        user_uuid,
    )

    return {
        "schema": 1,
        "preference":
            account.preference(
                user_uuid
            ),
    }


@router.get("/{user_uuid}/legacy/anyconnect")
def get_legacy_anyconnect(
    user_uuid: str,
    _: None = Depends(canary_auth),
    account: UniversalAccountReadAdapter = Depends(adapter),
):

    require_account(
        account,
        user_uuid,
    )

    return {
        "schema": 1,
        "anyconnect":
            account.legacy_anyconnect_state(
                user_uuid
            ),
    }
