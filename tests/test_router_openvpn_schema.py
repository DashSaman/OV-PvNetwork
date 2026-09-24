import unittest


class RouterOpenVpnSchemaContractTests(unittest.TestCase):
    def test_router_models_are_additive_and_never_store_plaintext_password(self):
        from backend.db.models import NodeRouterOpenVpnConfig, RouterOpenVpnCredential

        self.assertEqual(NodeRouterOpenVpnConfig.__tablename__, "node_router_openvpn")
        self.assertEqual(RouterOpenVpnCredential.__tablename__, "router_openvpn_credentials")

        config_columns = {column.name for column in NodeRouterOpenVpnConfig.__table__.columns}
        self.assertTrue(
            {
                "node_id",
                "enabled",
                "port",
                "protocol",
                "subnet",
                "capability_version",
                "last_verified_at",
                "last_error",
            }.issubset(config_columns)
        )

        credential_columns = {column.name for column in RouterOpenVpnCredential.__table__.columns}
        self.assertIn("password_hash", credential_columns)
        self.assertNotIn("password", credential_columns)
        # PVN-1012: reversible ciphertext is allowed; a plaintext column is not.
        self.assertIn("password_ciphertext", credential_columns)
        self.assertTrue({"user_uuid", "node_id", "router_username"}.issubset(credential_columns))

    def test_normal_node_openvpn_columns_are_unchanged(self):
        from backend.db.models import Node

        columns = {column.name for column in Node.__table__.columns}
        self.assertIn("ovpn_port", columns)
        self.assertIn("protocol", columns)
        self.assertNotIn("router_openvpn_port", columns)


if __name__ == "__main__":
    unittest.main()
