from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import User
from .user_ids import assign_public_id


@receiver(pre_save, sender=User)
def ensure_user_public_id(sender, instance, **kwargs):
    if not instance.public_id:
        assign_public_id(instance)
