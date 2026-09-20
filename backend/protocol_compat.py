from fastapi import Header, HTTPException


PVNETWORK_NODE_KEY_HEADER = "X-PVNetwork-Node-Key"
LEGACY_NODE_KEY_HEADER = "X-OV-Node-Key"


def resolve_node_key(
    pvnetwork_node_key: str | None,
    legacy_node_key: str | None,
) -> str:
    current = (pvnetwork_node_key or "").strip()
    legacy = (legacy_node_key or "").strip()

    if current and legacy and current != legacy:
        raise HTTPException(
            status_code=400,
            detail="Conflicting node key headers",
        )

    value = current or legacy
    if not value:
        raise HTTPException(
            status_code=422,
            detail="Node key header is required",
        )
    return value


def node_key_header(
    x_pvnetwork_node_key: str | None = Header(
        None,
        alias=PVNETWORK_NODE_KEY_HEADER,
    ),
    x_ov_node_key: str | None = Header(
        None,
        alias=LEGACY_NODE_KEY_HEADER,
    ),
) -> str:
    return resolve_node_key(
        x_pvnetwork_node_key,
        x_ov_node_key,
    )
