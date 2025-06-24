from pathlib import Path
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, LoginSerializer
from .pqcrypto_utils import sign_message

TERMS_PATH = Path(settings.BASE_DIR) / 'gotogym' / 'templates' / 'auth' / 'terms_and_conditions.html'

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={'terms_path': TERMS_PATH})
        if serializer.is_valid():
            user = serializer.save()
            return Response({'detail': 'Registro exitoso'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            access = str(refresh.access_token)
            signature = sign_message(access.encode())
            return Response({
                'access': access,
                'refresh': str(refresh),
                'signature': signature,
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
