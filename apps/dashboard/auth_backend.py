from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class ServerlessAuthBackend(ModelBackend):
    """
    Standard ModelBackend that retrieves users directly from Supabase PostgreSQL,
    with dual-support for logging in via either Username OR Email Address (case-insensitive).
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None
        try:
            users = UserModel._default_manager.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
            for user in users:
                if user.check_password(password) and self.user_can_authenticate(user):
                    return user
        except Exception:
            return None
        return None


    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            user = UserModel._default_manager.get(pk=user_id)
            return user if self.user_can_authenticate(user) else None
        except Exception:
            return None


