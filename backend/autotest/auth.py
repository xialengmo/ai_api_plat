# 作者: lxl
# 说明: 业务模块实现。
import os

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

TOKEN_SALT = "api_test_platform_auth"
TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "259200"))


def issue_auth_token(user):
    payload = {
        "uid": int(user.id),
        "username": str(user.username or ""),
        "is_staff": bool(user.is_staff),
        "is_superuser": bool(user.is_superuser),
    }
    return signing.dumps(payload, salt=TOKEN_SALT)


def parse_auth_token(token):
    return signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_TTL_SECONDS)


class SignedTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        raw = get_authorization_header(request)
        if not raw:
            return None
        try:
            text = raw.decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            raise AuthenticationFailed("Invalid authorization header") from exc
        if not text.startswith("Bearer "):
            return None
        token = text[7:].strip()
        if not token:
            raise AuthenticationFailed("Missing token")
        try:
            payload = parse_auth_token(token)
        except SignatureExpired as exc:
            raise AuthenticationFailed("Token expired") from exc
        except BadSignature as exc:
            raise AuthenticationFailed("Invalid token") from exc
        user_id = payload.get("uid")
        if not user_id:
            raise AuthenticationFailed("Invalid token payload")
        user = get_user_model().objects.filter(id=user_id, is_active=True).first()
        if user is None:
            raise AuthenticationFailed("User not found or disabled")
        return (user, None)
