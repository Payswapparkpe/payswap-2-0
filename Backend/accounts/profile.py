from django.core.exceptions import ValidationError

from audit.services import AuditService


class ProfileService:
    @staticmethod
    def update_contact(*, user, name: str, mobile: str, request=None):
        name = (name or "").strip()[:150]
        mobile = (mobile or "").strip()
        if mobile and not (len(mobile) == 10 and mobile.isdigit() and mobile[0] in "6789"):
            raise ValidationError("Enter a valid mobile number.")
        before = {"name": user.name, "mobile": user.mobile}
        user.name = name
        user.mobile = mobile
        user.save(update_fields=["name", "mobile"])
        AuditService.record(
            actor=user,
            action="profile.update",
            resource_type="user",
            resource_id=str(user.pk),
            before=before,
            after={"name": name, "mobile": mobile},
            request=request,
        )
        return user
