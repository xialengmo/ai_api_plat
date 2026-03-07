# 作者: lxl
# 说明: 业务模块实现。
from autotest.models import OperationAuditLog


class OperationAuditLogMiddleware:
    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    EXCLUDED_PATHS = {
        "/api/auth/login",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        method = str(getattr(request, "method", "") or "").upper()
        path = str(getattr(request, "path", "") or "")
        if method not in self.MUTATING_METHODS:
            return response
        if not path.startswith("/api/"):
            return response
        if path in self.EXCLUDED_PATHS:
            return response

        user = getattr(request, "user", None)
        username = ""
        user_id = None
        if user is not None and getattr(user, "is_authenticated", False):
            user_id = getattr(user, "id", None)
            username = str(getattr(user, "username", "") or "")

        detail = ""
        try:
            payload = getattr(response, "data", None)
            if isinstance(payload, dict):
                if payload.get("detail") is not None:
                    detail = str(payload.get("detail") or "")
                elif payload.get("message") is not None:
                    detail = str(payload.get("message") or "")
        except Exception:
            detail = ""

        try:
            OperationAuditLog.objects.create(
                user_id=user_id,
                username=username.strip()[:150] or None,
                method=method[:8],
                path=path[:255],
                status_code=getattr(response, "status_code", None),
                success=1 if int(getattr(response, "status_code", 0) or 0) < 400 else 0,
                detail=detail.strip()[:255] or None,
            )
        except Exception:
            # Audit should never block request flow.
            pass

        return response
