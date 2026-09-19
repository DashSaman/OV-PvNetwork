import os
os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD", "ci-password-not-production")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")

import unittest
from datetime import date
from unittest.mock import patch
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.engine import Base
from backend.db.models import Node, User, UserNode
from backend.node.assignment import validate_node_ids, set_user_nodes
from backend.schema._input import CreateUser
from backend.routers.node import _sync_existing_assignments_to_node


ROOT = Path(__file__).resolve().parents[1]


def make_node(node_id, name, *, status=True, drain=False, maintenance=False):
    return Node(
        id=node_id,
        name=name,
        address=f"192.0.2.{node_id}",
        tunnel_address=None,
        protocol="udp",
        ovpn_port=1194,
        port=9090,
        key="demo-key-not-secret",
        status=status,
        drain=drain,
        maintenance=maintenance,
    )


class UserCreationNodeSelectorTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_create_user_schema_accepts_optional_node_ids(self):
        field = CreateUser.model_fields["node_ids"]
        self.assertIsNone(field.default)

    def test_default_node_selection_uses_only_available_nodes(self):
        with self.Session() as db:
            db.add_all([
                make_node(1, "ready"),
                make_node(2, "offline", status=False),
                make_node(3, "draining", drain=True),
                make_node(4, "maintenance", maintenance=True),
            ])
            db.commit()
            self.assertEqual(validate_node_ids(db, None), [1])

    def test_explicit_maintenance_node_is_rejected(self):
        with self.Session() as db:
            db.add_all([make_node(1, "ready"), make_node(2, "maintenance", maintenance=True)])
            db.commit()
            with self.assertRaisesRegex(ValueError, "Maintenance"):
                validate_node_ids(db, [1, 2])

    def test_set_user_nodes_can_join_an_outer_transaction(self):
        with self.Session() as db:
            db.add_all([make_node(1, "one"), make_node(2, "two")])
            db.commit()
            set_user_nodes(db, "demo-user", [1, 2], commit=False)
            rows = db.query(UserNode).order_by(UserNode.node_id).all()
            self.assertEqual([row.node_id for row in rows], [1, 2])
            db.rollback()

    def test_panel_create_route_persists_and_provisions_selected_nodes(self):
        users = (ROOT / "backend/routers/users.py").read_text()
        create_section = users.split('@router.post("/", response_model=ResponseModel)', 1)[1].split('@router.put("/{uuid}"', 1)[0]
        self.assertIn("validate_node_ids", create_section)
        self.assertIn("request.node_ids", create_section)
        self.assertIn("set_user_nodes", create_section)
        self.assertIn("commit=False", create_section)
        self.assertIn("create_user_on_assigned_nodes", create_section)
        self.assertLess(create_section.index("validate_node_ids"), create_section.index("crud.create_user"))

    def test_add_user_modal_defaults_available_nodes_and_sends_node_ids(self):
        modal = (ROOT / "frontend/src/components/AddUserModal.jsx").read_text()
        page = (ROOT / "frontend/src/pages/UserManagement.jsx").read_text()
        self.assertIn("nodes = []", modal)
        self.assertIn("selectedNodeIds", modal)
        self.assertIn("node_ids: selectedNodeIds", modal)
        self.assertIn("node.maintenance", modal)
        self.assertIn("node.drain", modal)
        self.assertIn("nodes={nodes}", page)

    def test_ci_runs_user_creation_node_selector_browser_smoke(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("node tests/user-create-node-selector-smoke.mjs", workflow)

    def test_new_node_deploy_preserves_explicit_assignments_and_only_provisions_legacy_users(self):
        with self.Session() as db:
            old_node = make_node(1, "old")
            new_node = make_node(2, "new")
            legacy = User(
                uuid="legacy-user", name="legacy", total=0, used=0,
                expiry_date=date.today(), is_active=True, owner="owner", device_limit=1,
            )
            explicit = User(
                uuid="explicit-user", name="explicit", total=0, used=0,
                expiry_date=date.today(), is_active=True, owner="owner", device_limit=1,
            )
            db.add_all([old_node, new_node, legacy, explicit])
            db.add(UserNode(user_uuid=explicit.uuid, node_id=old_node.id))
            db.commit()

            with patch("backend.node.requests.NodeRequests") as requests_cls:
                request = requests_cls.return_value
                request.check_node.return_value = True
                request.create_user.return_value = True
                result = _sync_existing_assignments_to_node(db, new_node)

            self.assertEqual(result["assigned"], 0)
            self.assertEqual(result["attempted"], 1)
            self.assertEqual(result["created"], 1)
            self.assertEqual(result["failed"], 0)
            self.assertEqual(
                [row.node_id for row in db.query(UserNode).filter(UserNode.user_uuid == explicit.uuid).all()],
                [1],
            )
            self.assertEqual(
                db.query(UserNode).filter(UserNode.node_id == new_node.id).count(),
                0,
            )
            request.create_user.assert_called_once_with("legacy-new")

    def test_reconciler_never_widens_explicit_assignments(self):
        script = (ROOT / "scripts/pvnetwork-node-user-reconcile.py").read_text()
        self.assertNotIn("db.add(\n                        UserNode", script)
        self.assertIn("assignments_by_user", script)
        self.assertIn("desired_node_ids", script)


if __name__ == "__main__":
    unittest.main()
