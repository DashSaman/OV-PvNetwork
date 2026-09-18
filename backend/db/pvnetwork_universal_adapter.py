from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    AnyConnectCredential,
    User,
    UserNode,
)

from .pvnetwork_universal import (
    AccountDevice,
    AccountPreference,
    AccountProtocolEntitlement,
    DeviceCredential,
)


class UniversalAccountReadAdapter:
    """
    Read-only compatibility adapter.

    This class intentionally contains no create/update/delete,
    commit, flush, merge or credential-secret output path.
    """

    def __init__(self, session: Session):
        self.session = session


    def account_exists(
        self,
        user_uuid: str,
    ) -> bool:

        stmt = (
            select(User.uuid)
            .where(
                User.uuid == user_uuid
            )
            .limit(1)
        )

        return (
            self.session.execute(stmt)
            .scalar_one_or_none()
            is not None
        )


    def account_snapshot(
        self,
        user_uuid: str,
    ) -> dict[str, Any] | None:

        user_stmt = (
            select(User)
            .where(
                User.uuid == user_uuid
            )
            .limit(1)
        )

        user = (
            self.session.execute(
                user_stmt
            )
            .scalar_one_or_none()
        )

        if user is None:
            return None

        node_stmt = (
            select(UserNode.node_id)
            .where(
                UserNode.user_uuid
                == user_uuid
            )
            .order_by(
                UserNode.node_id
            )
        )

        node_ids = list(
            self.session.execute(
                node_stmt
            ).scalars()
        )

        return {
            "uuid": user.uuid,
            "name": user.name,
            "quota_total": user.total,
            "quota_used": user.used,
            "expiry_date": (
                user.expiry_date.isoformat()
                if user.expiry_date
                else None
            ),
            "is_active": user.is_active,
            "owner": user.owner,
            "device_limit": user.device_limit,
            "node_ids": node_ids,
        }


    def devices(
        self,
        user_uuid: str,
    ) -> list[dict[str, Any]]:

        stmt = (
            select(AccountDevice)
            .where(
                AccountDevice.user_uuid
                == user_uuid
            )
            .order_by(
                AccountDevice.id
            )
        )

        rows = (
            self.session.execute(stmt)
            .scalars()
            .all()
        )

        return [
            {
                "id": row.id,
                "device_uuid":
                    row.device_uuid,
                "name":
                    row.name,
                "device_type":
                    row.device_type,
                "is_active":
                    row.is_active,
                "created_at":
                    row.created_at,
                "updated_at":
                    row.updated_at,
                "last_seen_at":
                    row.last_seen_at,
            }
            for row in rows
        ]


    def credential_metadata(
        self,
        user_uuid: str,
    ) -> list[dict[str, Any]]:

        stmt = (
            select(DeviceCredential)
            .where(
                DeviceCredential.user_uuid
                == user_uuid
            )
            .order_by(
                DeviceCredential.id
            )
        )

        rows = (
            self.session.execute(stmt)
            .scalars()
            .all()
        )

        # Deliberately excludes secret_ciphertext.
        return [
            {
                "id": row.id,
                "credential_uuid":
                    row.credential_uuid,
                "device_id":
                    row.device_id,
                "protocol":
                    row.protocol,
                "credential_type":
                    row.credential_type,
                "external_ref":
                    row.external_ref,
                "secret_kid":
                    row.secret_kid,
                "secret_version":
                    row.secret_version,
                "is_active":
                    row.is_active,
                "created_at":
                    row.created_at,
                "updated_at":
                    row.updated_at,
                "rotated_at":
                    row.rotated_at,
                "revoked_at":
                    row.revoked_at,
            }
            for row in rows
        ]


    def protocol_entitlements(
        self,
        user_uuid: str,
    ) -> list[dict[str, Any]]:

        stmt = (
            select(
                AccountProtocolEntitlement
            )
            .where(
                AccountProtocolEntitlement.user_uuid
                == user_uuid
            )
            .order_by(
                AccountProtocolEntitlement.protocol
            )
        )

        rows = (
            self.session.execute(stmt)
            .scalars()
            .all()
        )

        return [
            {
                "protocol":
                    row.protocol,
                "enabled":
                    row.enabled,
                "created_at":
                    row.created_at,
                "updated_at":
                    row.updated_at,
            }
            for row in rows
        ]


    def preference(
        self,
        user_uuid: str,
    ) -> dict[str, Any]:

        stmt = (
            select(AccountPreference)
            .where(
                AccountPreference.user_uuid
                == user_uuid
            )
            .limit(1)
        )

        row = (
            self.session.execute(stmt)
            .scalar_one_or_none()
        )

        if row is None:
            return {
                "locale": "en-US",
                "timezone": None,
                "source": "fallback",
            }

        return {
            "locale": row.locale,
            "timezone": row.timezone,
            "source": "account",
        }


    def legacy_anyconnect_state(
        self,
        user_uuid: str,
    ) -> dict[str, Any]:

        stmt = (
            select(
                AnyConnectCredential.enabled,
                AnyConnectCredential.created_at,
                AnyConnectCredential.updated_at,
                AnyConnectCredential.password_changed_at,
                AnyConnectCredential.last_authenticated_at,
            )
            .where(
                AnyConnectCredential.user_uuid
                == user_uuid
            )
            .limit(1)
        )

        row = (
            self.session.execute(stmt)
            .mappings()
            .first()
        )

        if row is None:
            return {
                "present": False,
            }

        return {
            "present": True,
            "enabled":
                row["enabled"],
            "created_at":
                row["created_at"],
            "updated_at":
                row["updated_at"],
            "password_changed_at":
                row["password_changed_at"],
            "last_authenticated_at":
                row["last_authenticated_at"],
        }
