from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class ServerlessAuthBackend(ModelBackend):
    """
    Standard ModelBackend that retrieves users directly from the database (Supabase).
    """
    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            user = UserModel._default_manager.get(pk=user_id)
            return user if self.user_can_authenticate(user) else None
        except Exception:
            return None

