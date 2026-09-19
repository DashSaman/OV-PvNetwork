import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.node.assignment import replace_user_node_assignments


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
    def filter(self, *args, **kwargs):
        return self
    def order_by(self, *args, **kwargs):
        return self
    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, desired_rows):
        self.desired_rows = desired_rows
    def query(self, *args, **kwargs):
        return FakeQuery(self.desired_rows)


class FakeRequest:
    def __init__(self, *, reachable=True, create=True, status=True):
        self.reachable = reachable
        self.create_result = create
        self.status_result = status
        self.status_calls = []
        self.create_calls = []
        self.delete_calls = []
    def check_node(self):
        return self.reachable
    def create_user(self, name):
        self.create_calls.append(name)
        return self.create_result
    def change_user_status(self, name, status):
        self.status_calls.append((name, status))
        return self.status_result
    def delete_user(self, name):
        self.delete_calls.append(name)
        return True


def node(node_id, name, *, status=True, drain=False, maintenance=False):
    return SimpleNamespace(
        id=node_id,
        name=name,
        status=status,
        drain=drain,
        maintenance=maintenance,
        address=f"192.0.2.{node_id}",
        port=9090,
        key="demo-key-not-secret",
    )


class UserNodeAssignmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_removal_deactivates_profile_instead_of_deleting_it(self):
        n1, n2 = node(1, "one"), node(2, "two")
        req2 = FakeRequest()
        persisted = []
        with patch("backend.node.assignment.crud.get_user_by_uuid", return_value=SimpleNamespace(is_active=True)), \
             patch("backend.node.assignment.get_user_nodes", return_value=[n1, n2]), \
             patch("backend.node.assignment._node_request", side_effect=lambda item: req2 if item.id == 2 else FakeRequest()), \
             patch("backend.node.assignment.set_user_nodes", side_effect=lambda db, uuid, ids: persisted.append(list(ids))):
            result = await replace_user_node_assignments("u1", "alice", [1], FakeDB([n1]))
        self.assertEqual(result["removed_node_ids"], [2])
        self.assertEqual(req2.status_calls, [("alice-two", False)])
        self.assertEqual(req2.delete_calls, [])
        self.assertEqual(persisted, [[1]])

    async def test_readding_stale_profile_reuses_it_without_certificate_churn(self):
        n1, n2 = node(1, "one"), node(2, "two")
        req2 = FakeRequest(create=False, status=True)
        with patch("backend.node.assignment.crud.get_user_by_uuid", return_value=SimpleNamespace(is_active=True)), \
             patch("backend.node.assignment.get_user_nodes", return_value=[n1]), \
             patch("backend.node.assignment._node_request", side_effect=lambda item: req2 if item.id == 2 else FakeRequest()), \
             patch("backend.node.assignment.set_user_nodes"):
            result = await replace_user_node_assignments("u1", "alice", [1, 2], FakeDB([n1, n2]))
        self.assertEqual(req2.create_calls, ["alice-two"])
        self.assertEqual(req2.status_calls, [("alice-two", True)])
        self.assertEqual(result["provisioned_node_ids"], [2])
        self.assertEqual(result["pending_node_ids"], [])

    async def test_new_offline_node_is_rejected_before_mutation(self):
        n1, n2 = node(1, "one"), node(2, "two", status=False)
        with patch("backend.node.assignment.crud.get_user_by_uuid", return_value=SimpleNamespace(is_active=True)), \
             patch("backend.node.assignment.get_user_nodes", return_value=[n1]), \
             patch("backend.node.assignment.set_user_nodes") as persist:
            with self.assertRaisesRegex(ValueError, "Unavailable nodes"):
                await replace_user_node_assignments("u1", "alice", [1, 2], FakeDB([n1, n2]))
        persist.assert_not_called()


if __name__ == "__main__":
    unittest.main()
