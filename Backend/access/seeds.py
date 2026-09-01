from .models import Department, Permission, Role

PERMISSIONS = [
    ("portal.administration", "Access administration portal"),
    ("portal.employee", "Access employee portal"),
    ("portal.merchant", "Access merchant portal"),
    ("merchant.view", "View merchant"),
    ("merchant.review", "Review merchant"),
    ("merchant.assign", "Assign merchant"),
    ("merchant.suspend", "Suspend merchant"),
    ("kyc.approve", "Approve KYC"),
    ("kyb.approve", "Approve KYB"),
    ("order.create", "Create payment order"),
    ("order.review", "Review payment order"),
    ("order.approve", "Approve payment order"),
    ("order.reject", "Reject payment order"),
    ("order.request_changes", "Request changes on payment order"),
    ("order.cancel", "Cancel payment order"),
    ("order.amend", "Amend payment order"),
    ("role.manage", "Manage roles"),
    ("audit.view", "View audit"),
    ("security.manage", "Manage security"),
]

DEPARTMENTS = [
    ("kyc", "KYC"),
    ("operations", "Operations"),
    ("compliance", "Compliance"),
    ("support", "Support"),
]

ROLES = {
    "platform_admin": [
        "portal.administration",
        "merchant.view",
        "merchant.review",
        "merchant.assign",
        "merchant.suspend",
        "kyc.approve",
        "kyb.approve",
        "order.review",
        "order.approve",
        "order.reject",
        "order.request_changes",
        "order.cancel",
        "order.amend",
        "role.manage",
        "audit.view",
        "security.manage",
    ],
    "kyc": ["portal.employee", "merchant.view", "merchant.review", "kyc.approve", "kyb.approve"],
    "operations": [
        "portal.employee",
        "merchant.view",
        "order.review",
        "order.approve",
        "order.reject",
        "order.request_changes",
        "order.cancel",
        "order.amend",
    ],
    "compliance": ["portal.employee", "merchant.view", "merchant.review"],
    "support": ["portal.employee", "merchant.view"],
    "merchant": ["portal.merchant", "merchant.view", "order.create", "order.cancel", "order.amend"],
}


def seed_access_control() -> None:
    for slug, name in DEPARTMENTS:
        Department.objects.get_or_create(slug=slug, defaults={"name": name})
    for codename, name in PERMISSIONS:
        Permission.objects.get_or_create(codename=codename, defaults={"name": name})
    for slug, codes in ROLES.items():
        role, _ = Role.objects.get_or_create(slug=slug, defaults={"name": slug.replace("_", " ").title()})
        role.permissions.set(Permission.objects.filter(codename__in=codes))
