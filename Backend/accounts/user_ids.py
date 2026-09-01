"""Public user identifiers (PSU-000001)."""


def assign_public_id(user) -> str:
    if user.public_id:
        return user.public_id
    from merchants.services import next_public_id

    user.public_id = next_public_id("PSU", user.__class__)
    return user.public_id
