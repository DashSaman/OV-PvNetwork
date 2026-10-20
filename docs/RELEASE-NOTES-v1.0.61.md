# v1.0.61 candidate — PVN-1045

Since QA60: fix the actual subscription route's template call for the pinned Starlette API by passing request/name/context explicitly. Keep escaped content, assigned-node access, unavailable-node behavior, HTTP404 boundaries and the60 dependency fix. [Actual route tests and remaining gates](VALIDATION-v1.0.61.md).

No schema/node/VPN setting changes. CI/public artifact checks and owner-authorized deployment with fresh recoverable backup/ready rollback are required before completion; this is not a Stable promotion. Existing synthetic [illustrated guide](UI-GUIDE.md) remains applicable to the unchanged design.
