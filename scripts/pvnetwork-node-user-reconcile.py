#!/opt/pvnetwork-panel/.venv/bin/python3

import sys
import argparse
from pathlib import Path
source_root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(source_root) if (source_root/'backend').is_dir() else "/opt/pvnetwork-panel")

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


def main(node_id=None):

    if node_id is not None and (type(node_id) is not int or node_id<1):
        raise ValueError('positive explicit node ID required')

    db = SessionLocal()

    try:
        users = (
            db.query(User)
            .filter(User.is_active.is_(True))
            .order_by(User.id)
            .all()
        )

        node_query=db.query(Node)
        if node_id is not None:
            # Manual repair can prepare an assigned drained/disabled node;
            # it never changes its eligibility flags or the target scope.
            node_query=node_query.filter(Node.id==node_id)
        else:
            node_query=node_query.filter(
                Node.status.is_(True),
                Node.drain.is_(False),
                Node.maintenance.is_(False),
            )
        nodes=node_query.order_by(Node.id).all()
        if node_id is not None and not nodes:
            print('RECONCILE_RESULT=FAIL REASON=target_unavailable',flush=True)
            return 1

        assignment_rows = db.query(
            UserNode.user_uuid, UserNode.node_id
        ).all()
        assignments_by_user = {}
        for user_uuid, node_id in assignment_rows:
            assignments_by_user.setdefault(user_uuid, set()).add(int(node_id))

        print(
            f"ACTIVE_USERS={len(users)} ACTIVE_NODES={len(nodes)}",
            flush=True,
        )

        total_failed = 0

        for node in nodes:
            desired_users = []
            for user in users:
                desired_node_ids = assignments_by_user.get(user.uuid)
                # Legacy users without explicit assignment rows preserve the
                # pre-selector all-available-node behavior. Explicit rows are
                # authoritative and must never be widened by reconciliation.
                if not desired_node_ids or int(node.id) in desired_node_ids:
                    desired_users.append(user)

            req = NodeRequests(
                address=node.address,
                port=node.port,
                api_key=node.key,
                tunnel_address=node.tunnel_address or node.address,
                protocol=node.protocol or "udp",
                ovpn_port=int(node.ovpn_port or 1194),
                set_new_setting=False,
            )

            try:
                reachable = req.check_node()
            except Exception:
                reachable = False

            if not reachable:
                print(
                    f"NODE={node.name} REACHABLE=NO DESIRED={len(desired_users)}",
                    flush=True,
                )
                total_failed += max(1,len(desired_users))
                continue

            ok = 0
            failed = 0

            for user in desired_users:
                client = f"{user.name}-{node.name}"
                if profile_valid(req, client):
                    ok += 1
                    continue

                try:
                    req.create_user(client)
                except Exception:
                    pass

                if profile_valid(req, client):
                    ok += 1
                else:
                    failed += 1
                    total_failed += 1
                    print("FAIL", node.name, client, flush=True)

            print(
                f"NODE={node.name} DESIRED={len(desired_users)} "
                f"PROFILE_OK={ok} FAILED={failed}",
                flush=True,
            )

        if total_failed:
            print(
                f"RECONCILE_RESULT=FAIL FAILED={total_failed}",
                flush=True,
            )
            return 1

        print("RECONCILE_RESULT=PASS", flush=True)
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description='Reconcile existing user assignments; optional explicit node scope')
    parser.add_argument('--node-id',type=int)
    arguments=parser.parse_args()
    if arguments.node_id is not None and arguments.node_id<1:parser.error('positive --node-id required')
    raise SystemExit(
        main(arguments.node_id)
    )
