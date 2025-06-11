from pathlib import Path
import hashlib

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework import serializers

from .models import User

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    accepted_terms = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = ("email", "full_name", "password", "password2", "accepted_terms")

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError("Las contraseñas no coinciden")
        if not data.get("accepted_terms"):
            raise serializers.ValidationError(
                "Debes aceptar los términos y condiciones para continuar"
            )
        return data

    def create(self, validated_data):
        validated_data.pop("password2")
        terms_path = self.context.get("terms_path")
        terms_text = Path(terms_path).read_text(encoding="utf-8")
        terms_hash = hashlib.sha512(terms_text.encode()).hexdigest()
        user = User.objects.create(
            email=validated_data["email"],
            full_name=validated_data["full_name"],
            accepted_terms=True,
            terms_accepted_at=timezone.now(),
            terms_hash=terms_hash,
            password=make_password(validated_data["password"]),
        )
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(email=data.get("email"), password=data.get("password"))
        if not user:
            raise serializers.ValidationError("Credenciales incorrectas")
        data["user"] = user
        return data
