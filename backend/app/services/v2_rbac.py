from __future__ import annotations

ALL_V2_PERMISSIONS: tuple[str, ...] = (
    "inventory:read",
    "inventory:write",
    "sales:read",
    "sales:write",
    "purchasing:read",
    "purchasing:write",
    "customers:read",
    "customers:write",
    "finance:read",
    "exports:sales",
    "exports:purchasing",
    "exports:finance",
    "exports:inventory",
    "audit:read",
    "ai:read",
    "ai:write",
    "confirmations:read",
    "confirmations:approve",
    "dashboard:read",
)

ROLE_PERMISSION_MATRIX: dict[str, tuple[str, ...]] = {
    "owner": ALL_V2_PERMISSIONS,
    "manager": ALL_V2_PERMISSIONS,
    "clerk": (
        "inventory:read",
        "sales:read",
        "sales:write",
        "customers:read",
        "customers:write",
        "ai:read",
        "ai:write",
        "confirmations:read",
        "dashboard:read",
    ),
    "finance": (
        "inventory:read",
        "sales:read",
        "purchasing:read",
        "customers:read",
        "finance:read",
        "exports:sales",
        "exports:finance",
        "audit:read",
        "ai:read",
        "confirmations:read",
        "dashboard:read",
    ),
}

ROLE_LABELS: dict[str, str] = {
    "owner": "老板",
    "manager": "店长",
    "clerk": "店员",
    "finance": "财务",
}


def permissions_for_role(role_key: str | None) -> list[str]:
    normalized = (role_key or "clerk").strip().lower()
    permissions = ROLE_PERMISSION_MATRIX.get(normalized, ROLE_PERMISSION_MATRIX["clerk"])
    return list(dict.fromkeys(permissions))


def role_label(role_key: str | None) -> str:
    return ROLE_LABELS.get((role_key or "").strip().lower(), "店员")
