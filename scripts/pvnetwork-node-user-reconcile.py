#!/opt/pvnetwork-panel/.venv/bin/python3

import sys
sys.path.insert(0, "/opt/pvnetwork-panel")

from backend.db.engine import SessionLocal
from backend.db.models import Node, User, UserNode
from backend.node.requests import NodeRequests


def profile_valid(req, client):

    try:
        response = (
            req.download_ovpn_client(
                client
            )
        )

        if not response:
            return False

        raw = getattr(
            response,
            "content",
            None,
        )

        if raw is None:
            raw = getattr(
                response,
                "body",
                b"",
            )

        if isinstance(raw, str):
            raw = raw.encode()

        if len(raw or b"") < 500:
            return False

        text = bytes(raw).decode(
            "utf-8",
            errors="ignore",
        ).lower()

        return all(
            x in text
            for x in (
                "<ca>",
                "<cert>",
                "<key>",
            )
        )

    except Exception:
        return False


def main():

    db = SessionLocal()

    try:
        users = (
            db.query(User)
            .filter(
                User.is_active.is_(True)
            )
            .order_by(User.id)
            .all()
        )

        nodes = (
            db.query(Node)
            .filter(
                Node.status.is_(True)
            )
            .order_by(Node.id)
            .all()
        )

        print(
            f"ACTIVE_USERS={len(users)} "
            f"ACTIVE_NODES={len(nodes)}",
            flush=True,
        )

        total_failed = 0

        for node in nodes:

            added = 0

            for user in users:

                assignment = (
                    db.query(UserNode)
                    .filter(
                        UserNode.user_uuid
                        == user.uuid,

                        UserNode.node_id
                        == node.id,
                    )
                    .first()
                )

                if not assignment:

                    db.add(
                        UserNode(
                            user_uuid=user.uuid,
                            node_id=node.id,
                        )
                    )

                    added += 1

            db.commit()

            req = NodeRequests(
                address=node.address,
                port=node.port,
                api_key=node.key,
                tunnel_address=(
                    node.tunnel_address
                    or node.address
                ),
                protocol=(
                    node.protocol
                    or "udp"
                ),
                ovpn_port=int(
                    node.ovpn_port
                    or 1194
                ),
                set_new_setting=False,
            )

            try:
                reachable = (
                    req.check_node()
                )
            except Exception:
                reachable = False

            if not reachable:

                print(
                    f"NODE={node.name} "
                    "REACHABLE=NO",
                    flush=True,
                )

                total_failed += len(users)
                continue

            ok = 0
            failed = 0

            for user in users:

                client = (
                    f"{user.name}-{node.name}"
                )

                if profile_valid(
                    req,
                    client,
                ):

                    ok += 1
                    continue

                try:
                    req.create_user(
                        client
                    )
                except Exception:
                    pass

                if profile_valid(
                    req,
                    client,
                ):

                    ok += 1

                else:

                    failed += 1
                    total_failed += 1

                    print(
                        "FAIL",
                        node.name,
                        client,
                        flush=True,
                    )

            print(
                f"NODE={node.name} "
                f"ADDED={added} "
                f"PROFILE_OK={ok} "
                f"FAILED={failed}",
                flush=True,
            )

        if total_failed:

            print(
                "RECONCILE_RESULT=FAIL "
                f"FAILED={total_failed}",
                flush=True,
            )

            return 1

        print(
            "RECONCILE_RESULT=PASS",
            flush=True,
        )

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
