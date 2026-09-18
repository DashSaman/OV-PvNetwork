from __future__ import annotations

import json
import sys

from backend.operations.bandwidth_control import reconcile_persisted_settings


def main() -> int:
    result = reconcile_persisted_settings()
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    if not result.get("enabled"):
        return 0
    return 0 if all(item.get("ok") for item in result.get("results", [])) else 1


if __name__ == "__main__":
    raise SystemExit(main())
