"""Role-Based Access Control definitions."""
from enum import Enum
from typing import Set


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    AUDITOR = "auditor"
    VERIFIER = "verifier"
    READ_ONLY = "read_only"
    EXTERNAL_REVIEWER = "external_reviewer"  # least-privilege, view-only (partner review)


# Permission strings used across admin/control-plane routes.
class Permission(str, Enum):
    KEYS_MANAGE = "keys:manage"          # create/rotate/revoke/retire signing keys
    APIKEYS_MANAGE = "apikeys:manage"    # create/revoke API keys
    APIKEYS_READ = "apikeys:read"        # VIEW api keys (no secrets)
    TENANTS_MANAGE = "tenants:manage"    # create/list tenants
    TENANTS_READ = "tenants:read"        # VIEW tenants
    AUDIT_READ = "audit:read"            # read audit log
    FEA_WRITE = "fea:write"              # generate FEAs
    FEA_READ = "fea:read"                # list/read FEAs
    FEA_VERIFY = "fea:verify"            # verify FEAs
    WEBHOOKS_MANAGE = "webhooks:manage"  # manage webhook subscriptions
    WEBHOOKS_READ = "webhooks:read"      # VIEW webhook subscriptions


ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.SUPER_ADMIN: set(Permission),  # all permissions, all tenants
    Role.TENANT_ADMIN: {
        Permission.KEYS_MANAGE,
        Permission.APIKEYS_MANAGE,
        Permission.APIKEYS_READ,
        Permission.TENANTS_MANAGE,
        Permission.TENANTS_READ,
        Permission.AUDIT_READ,
        Permission.FEA_WRITE,
        Permission.FEA_READ,
        Permission.FEA_VERIFY,
        Permission.WEBHOOKS_MANAGE,
        Permission.WEBHOOKS_READ,
    },
    Role.AUDITOR: {
        Permission.AUDIT_READ,
        Permission.TENANTS_READ,
        Permission.APIKEYS_READ,
        Permission.FEA_READ,
        Permission.FEA_VERIFY,
    },
    Role.VERIFIER: {
        Permission.FEA_VERIFY,
    },
    Role.READ_ONLY: {
        Permission.FEA_READ,
    },
    # External Reviewer (Read Only): VIEW-only across the control plane.
    # Holds NO *_MANAGE / *_WRITE permission, so every write route returns 403.
    Role.EXTERNAL_REVIEWER: {
        Permission.TENANTS_READ,
        Permission.APIKEYS_READ,
        Permission.AUDIT_READ,
        Permission.FEA_READ,
        Permission.FEA_VERIFY,
        Permission.WEBHOOKS_READ,
    },
}


def role_has_permission(role: str, permission: Permission) -> bool:
    try:
        r = Role(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(r, set())


def is_super_admin(role: str) -> bool:
    return role == Role.SUPER_ADMIN.value
