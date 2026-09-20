from fastapi import HTTPException


def require_interactive_main_admin(user: dict) -> None:
    if user.get("type") != "main_admin" or user.get("auth_kind") == "api_token":
        raise HTTPException(403, "Interactive main administrator required")
