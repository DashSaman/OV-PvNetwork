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

    def get_user_identity(self, name: str) -> dict:
        api = f"http://{self.address}/sync/user/{name}/identity"
        try:
            response = requests.get(api, headers=self.headers, timeout=(2, 6))
            response.raise_for_status()
            payload = response.json()
            if not payload.get("success") or not isinstance(payload.get("data"), dict):
                return {}
            raw = payload["data"]
            return {
                "exists": bool(raw.get("exists")),
                "valid_certificate": bool(raw.get("valid_certificate")),
                "profile_exists": bool(raw.get("profile_exists")),
                "ccd_enabled": bool(raw.get("ccd_enabled")),
                "connected": bool(raw.get("connected")),
                "client_name": name if str(raw.get("client_name") or name) != name else str(raw.get("client_name") or name),
                "capability_version": str(raw.get("capability_version") or ""),
            }
        except Exception as exc:
            logger.error(f"Error inspecting user identity on node {self.address}: {exc}")
            return {}

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

    def get_users_usage(self, timeout=(2, 8)) -> dict | bool:
        api = f"http://{self.address}/sync/usage"
        try:
            response = requests.get(api, headers=self.headers, timeout=timeout).json()
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

    def _router_openvpn_request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        timeout=(2, 8),
    ) -> dict:
        api = f"http://{self.address}/sync/router-openvpn/{path.lstrip('/')}"
        try:
            response = requests.request(
                method,
                api,
                headers=self.headers,
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            logger.error(
                f"Router OpenVPN request failed on node {self.address}: {exc}"
            )
            return {
                "ok": False,
                "capable": True,
                "upgrade_required": False,
                "status_code": 0,
                "msg": "Node router capability is unreachable",
                "data": None,
            }

        if response.status_code == 404:
            return {
                "ok": False,
                "capable": False,
                "upgrade_required": True,
                "status_code": 404,
                "msg": "Router OpenVPN capability is not installed",
                "data": None,
            }

        try:
            body = response.json()
        except ValueError:
            body = {}
        data = body.get("data") if isinstance(body, dict) else None
        success = bool(response.ok and isinstance(body, dict) and body.get("success"))
        capable = not bool(isinstance(data, dict) and data.get("capable") is False)
        return {
            "ok": success,
            "capable": capable,
            "upgrade_required": bool(
                isinstance(data, dict) and data.get("upgrade_required")
            ),
            "status_code": int(response.status_code),
            "msg": str(body.get("msg") or body.get("detail") or "") if isinstance(body, dict) else "",
            "data": data,
        }

    def router_openvpn_status(self) -> dict:
        return self._router_openvpn_request("GET", "status")

    def router_openvpn_preflight(
        self, port: int, protocol: str, subnet: str
    ) -> dict:
        return self._router_openvpn_request(
            "POST",
            "preflight",
            payload={
                "enabled": True,
                "port": int(port),
                "protocol": str(protocol),
                "subnet": str(subnet),
            },
        )

    def router_openvpn_config(
        self, *, enabled: bool, port: int, protocol: str, subnet: str
    ) -> dict:
        return self._router_openvpn_request(
            "PUT",
            "config",
            payload={
                "enabled": bool(enabled),
                "port": int(port),
                "protocol": str(protocol),
                "subnet": str(subnet),
            },
            timeout=(3, 65),
        )

    def router_openvpn_set_credential(
        self, *, cn: str, username: str, verifier: str, enabled: bool
    ) -> dict:
        return self._router_openvpn_request(
            "PUT",
            "credential",
            payload={
                "cn": str(cn),
                "username": str(username),
                "verifier": str(verifier),
                "enabled": bool(enabled),
            },
        )

    def router_openvpn_profile(self, cn: str) -> Response | None:
        api = f"http://{self.address}/sync/router-openvpn/profile/{cn}"
        try:
            response = requests.request(
                "GET", api, headers=self.headers, timeout=(2, 8)
            )
        except requests.RequestException as exc:
            logger.error(
                f"Router OpenVPN profile download failed on node {self.address}: {exc}"
            )
            return None
        if response.status_code != 200:
            return None
        return Response(
            content=response.content,
            media_type="application/x-openvpn-profile",
            headers={
                "Content-Disposition": f"attachment; filename={cn}.router.ovpn"
            },
        )

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
