import requests

# PVNETWORK_FAILOPEN_EVENTLOOP_V1
from fastapi.responses import Response
from backend.logger import logger


class NodeRequests:
    """Handles requests to the node API."""

    def __init__(
        self,
        address: str,
        port: int,
        api_key: str,
        tunnel_address: str | None = None,
        protocol: str = "tcp",
        ovpn_port: int = 1194,
        set_new_setting: bool = False,
    ):
        self.address = f"{address}:{port}"
        self.headers = {"key": api_key, "api-key": api_key}
        self.tunnel_address = tunnel_address or address
        self.protocol = protocol
        self.ovpn_port = ovpn_port
        self.set_new_setting = set_new_setting

    def check_node(self) -> bool:
        """Check node status."""
        api = f"http://{self.address}/sync/status"

        try:
            data = {
                "tunnel_address": self.tunnel_address,
                "protocol": self.protocol,
                "ovpn_port": self.ovpn_port,
                "set_new_setting": self.set_new_setting,
            }

            response = requests.get(
                api,
                headers=self.headers,
                json=data,
                timeout=(3, 10),
            )

            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                return True

            logger.error(
                f"Node {self.address} returned: "
                f"{result.get('msg')}"
            )
            return False

        except Exception as e:
            logger.error(
                f"Error checking node {self.address}: {e}"
            )
            return False


    def get_node_info(self) -> dict:
        api = f"http://{self.address}/sync/status"
        try:
            data = {
                "tunnel_address": self.tunnel_address,
                "protocol": self.protocol,
                "ovpn_port": self.ovpn_port,
                "set_new_setting": self.set_new_setting,
            }
            response = requests.get(
                api, headers=self.headers, json=data, timeout=(2, 4)
            ).json()
            if response.get("success"):
                return response.get("data")
            else:
                logger.error(
                    f"Failed to get node info on {self.address}: {response.get('msg')}"
                )
                return {}
        except Exception as e:
            logger.error(f"Error getting node info on {self.address}: {e}")
            return {}

    def create_user(self, name: str) -> bool:
        api = f"http://{self.address}/sync/user"
        data = {"name": name}
        try:
            response = requests.post(
                api, headers=self.headers, json=data, timeout=(3, 10)
            ).json()
            if response.get("success"):
                return True
            else:
                logger.error(
                    f"Failed to create user on node {self.address}: {response.get('msg')}"
                )
                return False
        except Exception as e:
            logger.error(f"Error creating user on node {self.address}: {e}")
            return False

    def change_user_status(self, name, status):
        api = f"http://{self.address}/sync/user"
        try:
            data = {"name": name, "status": "activate" if status else "deactivate"}
            response = requests.put(
                api, headers=self.headers, json=data, timeout=(2, 6)
            ).json()

            if response.get("success"):
                return True
            else:
                logger.error(
                    f"Failed to change user status on node {self.address}: {response.get('msg')}"
                )
                return False
        except Exception as e:
            logger.error(f"Error change user status on node {self.address}: {e}")
            return False

    def download_ovpn_client(self, name: str) -> Response:
        api = f"http://{self.address}/sync/download/ovpn/{name}"
        try:
            response = requests.get(api, headers=self.headers, timeout=(2, 8))
            if response.status_code == 200:
                return Response(
                    content=response.content,
                    media_type="application/x-openvpn-profile",
                    headers={
                        "Content-Disposition": f"attachment; filename={name}.ovpn"
                    },
                )
        except Exception as e:
            logger.error(f"Error downloading OVPN client from node {self.address}: {e}")
        return None

    def delete_user(self, name: str) -> bool:
        api = f"http://{self.address}/sync/user/{name}"
        try:
            response = requests.delete(
                api, headers=self.headers, timeout=(3, 10)
            ).json()
            if response.get("success"):
                return True
            else:
                logger.error(
                    f"Failed to delete user on node {self.address}: {response.get('msg')}"
                )
                return False
        except Exception as e:
            logger.error(f"Error deleting user on node {self.address}: {e}")
            return False

    def get_users_usage(self) ->dict | bool:
        api = f"http://{self.address}/sync/usage"
        try:
            response = requests.get(api, headers=self.headers, timeout=(2, 8)).json()
            if response.get("success"):
                logger.info(f"get users usage on node {self.address}: {response.get('msg')}")
                return response.get("data")
            else:
                logger.error(
                    f"Failed to get users usage on node {self.address}: {response.get('msg')}"
                )
                return False
        except Exception as e:
            logger.error(f"Error when getting users usage on node {self.address}: {e}")
            return False

    # ========================================================
    # PVNETWORK_EMERGENCY_BANDWIDTH_CONTROL_V1
    # ========================================================

    def _bandwidth_call(self, method: str, path: str, payload: dict | None = None) -> dict:
        api = f"http://{self.address}/sync/bandwidth/{path.lstrip('/')}"
        try:
            response = requests.request(
                method,
                api,
                headers=self.headers,
                json=payload,
                timeout=(3, 12),
            )
            try:
                body = response.json()
            except Exception:
                body = {"success": False, "msg": response.text[:500]}
            return {
                "ok": bool(response.ok and body.get("success")),
                "status_code": int(response.status_code),
                "msg": body.get("msg") or body.get("detail") or "",
                "data": body.get("data"),
            }
        except Exception as exc:
            logger.error(
                f"Bandwidth API error on node {self.address}: {exc}"
            )
            return {
                "ok": False,
                "status_code": 0,
                "msg": f"{type(exc).__name__}: {exc}",
                "data": None,
            }

    def bandwidth_preview(self, payload: dict) -> dict:
        return self._bandwidth_call("POST", "preview", payload)

    def bandwidth_apply(self, payload: dict) -> dict:
        return self._bandwidth_call("PUT", "policy", payload)

    def bandwidth_disable(self, payload: dict | None = None) -> dict:
        return self._bandwidth_call("POST", "disable", payload or {})

    def bandwidth_status(self) -> dict:
        return self._bandwidth_call("GET", "status")
