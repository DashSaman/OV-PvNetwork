from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

TrafficAction = Literal["preserve", "reset", "add"]


@dataclass(frozen=True)
class RenewalPlan:
    expiry_date: date
    total: int
    used: int
    activate: bool
    traffic_action: TrafficAction
    add_traffic: int


def build_renewal_plan(
    *,
    today: date,
    current_expiry: date,
    total: int,
    used: int,
    duration_days: int,
    traffic_action: TrafficAction,
    add_traffic: int = 0,
) -> RenewalPlan:
    duration_days = int(duration_days)
    total = max(0, int(total or 0))
    used = max(0, int(used or 0))
    add_traffic = max(0, int(add_traffic or 0))

    if duration_days < 1 or duration_days > 3650:
        raise ValueError("duration_days must be between 1 and 3650")
    if traffic_action not in {"preserve", "reset", "add"}:
        raise ValueError("invalid traffic_action")
    if total <= 0 and traffic_action != "preserve":
        raise ValueError("unlimited users only support preserve traffic action")
    if traffic_action == "add" and add_traffic <= 0:
        raise ValueError("add_traffic must be positive")

    base = max(today, current_expiry)
    new_expiry = base + timedelta(days=duration_days)
    new_total = total + add_traffic if traffic_action == "add" else total
    new_used = 0 if traffic_action == "reset" else used

    if new_total > 0 and new_used >= new_total:
        raise ValueError(
            "renewal would remain traffic-limited; reset usage or add more traffic"
        )

    return RenewalPlan(
        expiry_date=new_expiry,
        total=new_total,
        used=new_used,
        activate=True,
        traffic_action=traffic_action,
        add_traffic=add_traffic,
    )
