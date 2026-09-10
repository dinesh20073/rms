from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class ServerlessAuthBackend(ModelBackend):
    """
    Robust Auth Backend for Serverless environments.
    When a container starts with a fresh ephemeral SQLite DB,
    automatically ensures migrations and seed users exist so the user is never logged out.
    """
    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            user = UserModel._default_manager.get(pk=user_id)
            return user if self.user_can_authenticate(user) else None
        except Exception:
            try:
                from django.core.management import call_command
                call_command('migrate', interactive=False)
                from seed_data import seed
                seed()
                user = UserModel._default_manager.get(pk=user_id)
                return user if self.user_can_authenticate(user) else None
            except Exception:
                return None
