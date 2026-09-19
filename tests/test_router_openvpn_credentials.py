import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.models import Node, RouterOpenVpnCredential, User


class RouterOpenVpnCredentialTests(unittest.TestCase):
    def test_generated_router_username_is_routeros_safe(self):
        from backend.router_openvpn.credentials import generate_router_username

        value = generate_router_username(
            "12345678-1234-5678-1234-567812345678",
            42,
        )
        self.assertGreaterEqual(len(value), 1)
        self.assertLessEqual(len(value), 27)
        self.assertTrue(value.replace("_", "").isalnum())
        self.assertEqual(value, generate_router_username(
            "12345678-1234-5678-1234-567812345678",
            42,
        ))

    def test_hash_verifies_without_plaintext_roundtrip(self):
        from backend.router_openvpn.credentials import (
            hash_router_password,
            verify_router_password,
        )

        plaintext = "S3cure-Example-Password"
        encoded = hash_router_password(plaintext)
        self.assertTrue(encoded.startswith("scrypt$32768$8$1$"))
        self.assertTrue(verify_router_password(plaintext, encoded))
        self.assertFalse(verify_router_password("wrong", encoded))
        self.assertNotIn(plaintext, encoded)

    def test_rotate_returns_secret_once_but_database_stores_only_verifier(self):
        from backend.router_openvpn.credentials import rotate_router_credential

        engine = create_engine("sqlite+pysqlite:///:memory:")
        User.__table__.create(engine)
        Node.__table__.create(engine)
        RouterOpenVpnCredential.__table__.create(engine)
        with Session(engine) as db:
            db.add(User(
                uuid="12345678-1234-5678-1234-567812345678",
                name="routeruser",
                expiry_date=date(2030, 1, 1),
                owner="owner",
                is_active=True,
            ))
            db.add(Node(
                id=42,
                name="node42",
                address="192.0.2.42",
                protocol="udp",
                ovpn_port=1194,
                port=9090,
                key="test-key",
                status=True,
            ))
            db.commit()

            result = rotate_router_credential(
                db,
                user_uuid="12345678-1234-5678-1234-567812345678",
                node_id=42,
            )
            db.commit()
            row = db.get(
                RouterOpenVpnCredential,
                ("12345678-1234-5678-1234-567812345678", 42),
            )

            self.assertEqual(result["router_username"], row.router_username)
            self.assertTrue(result["enabled"])
            self.assertGreaterEqual(len(result["password"]), 32)
            self.assertNotEqual(result["password"], row.password_hash)
            self.assertNotIn(result["password"], row.password_hash)
            self.assertFalse(hasattr(row, "password"))
            self.assertFalse(hasattr(row, "password_ciphertext"))


if __name__ == "__main__":
    unittest.main()
