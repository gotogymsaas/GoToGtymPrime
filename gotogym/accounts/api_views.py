from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken


def _developer_role(user):
    if user.is_superuser:
        return "admin"
    if user.is_staff:
        return "gym"
    return "user"


def _developer_permissions(role):
    permissions = {
        "admin": ["dashboard", "integrations", "applications", "consents", "users"],
        "gym": ["dashboard", "business-wellbeing", "business-members", "integrations", "applications", "consents"],
        "user": ["dashboard", "smartwatch", "app-gotogym", "business-members", "consents"],
    }
    return permissions[role]


def _developer_user_payload(user):
    role = _developer_role(user)
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": role,
        "permissions": _developer_permissions(role),
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def developer_login(request):
    identifier = (
        request.data.get("email")
        or request.data.get("username")
        or request.data.get("user")
        or ""
    ).strip()
    password = request.data.get("password") or ""

    User = get_user_model()
    user = User.objects.filter(
        Q(email__iexact=identifier) | Q(username__iexact=identifier)
    ).first()

    if user is None or not user.is_active or not user.check_password(password):
        return Response({"detail": "Credenciales incorrectas"}, status=400)

    refresh = RefreshToken.for_user(user)
    payload = _developer_user_payload(user)
    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": payload,
            "data": {
                "token": str(refresh.access_token),
                "refreshToken": str(refresh),
                "role": payload["role"],
                "user": payload,
                "permissions": payload["permissions"],
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def developer_users(request):
    if not request.user.is_staff:
        return Response({"detail": "No autorizado"}, status=403)

    User = get_user_model()
    users = User.objects.order_by("date_joined", "id")
    return Response({"data": [_developer_user_payload(user) for user in users]})
