"""PVN-202/PVN-203 — expiry and traffic-threshold renewal notifications.

Pure functions build the alert set from user rows; the Telegram monitor owns
delivery and dedup state, exactly like the existing node DOWN/UP alerts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Days-before-expiry stages that each fire once per stage per user.
EXPIRY_STAGES = (7, 3, 1)


@dataclass
class RenewalAlert:
    key: str
    message: str


def _traffic_stage(used: int | None, total: int | None) -> int | None:
    """Highest crossed threshold (80, 90, 100 percent) or None."""
    if not total or total <= 0 or used is None or used <= 0:
        return None
    percent = used * 100.0 / total
    for stage in (100, 90, 80):
        if percent >= stage:
            return stage
    return None


def build_renewal_alerts(users, today: date | None = None) -> list[RenewalAlert]:
    """Build expiry/traffic renewal alerts for active users.

    ``users`` rows expose name, expiry_date, total, used, is_active.
    Keys encode the user+stage so the monitor's transition dedup fires each
    alert once and clears it when the condition resolves (renewal or reset).
    """
    today = today or date.today()
    alerts: list[RenewalAlert] = {}
    for user in users:
        if not bool(getattr(user, "is_active", False)):
            continue
        name = getattr(user, "name", None)
        if not name:
            continue

        expiry = getattr(user, "expiry_date", None)
        if expiry is not None:
            remaining = (expiry - today).days
            label = None
            for stage in sorted(EXPIRY_STAGES):
                if remaining <= stage:
                    # The final day carries its own key so the "today" alert
                    # can fire even if the 1-day alert already fired.
                    label = "0" if remaining == 0 else str(stage)
                    when = (
                        "امروز آخرین روز اشتراک است"
                        if remaining == 0
                        else f"{remaining} روز تا پایان اشتراک"
                    )
                    break
            if label is not None:
                alerts[f"renew:e:{name}:{label}"] = (
                    f"⏳ یادآوری تمدید: {name} — {when}. برای جلوگیری از قطع سرویس تمدید شود."
                )

        used = getattr(user, "used", None)
        total = getattr(user, "total", None)
        stage = _traffic_stage(used, total)
        if stage is not None:
            alerts[f"renew:t:{name}:{stage}"] = (
                f"📊 مصرف {name} به {stage}٪ حجم اشتراک رسیده است."
            )
    return [RenewalAlert(key=key, message=message) for key, message in alerts.items()]


def build_renewal_transition_messages(old: dict, new: dict) -> list[str]:
    """Emit messages for alerts that appear; silence when they clear.

    Reuses the DOWN/UP transition semantics: appearing alerts notify once;
    cleared alerts vanish silently so a renewal or reset does not spam.
    """
    old_keys = {key for key in old if key.startswith("renew:")}
    new_keys = {key for key in new if key.startswith("renew:")}
    return [new[key] for key in sorted(new_keys - old_keys)]
