from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_decode
from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from core.mail import send_verification_email
from .models import Profile
from .serializers import CustomTokenObtainPairSerializer, RegisterSerializer, ProfileSerializer, UserSerializer

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        user = self.serializer_class.Meta.model.objects.get(
            email=resp.data["email"]
        )
        user.is_active = False
        send_verification_email(user)
        refresh = RefreshToken.for_user(user)
        resp.data["refresh"] = str(refresh)
        resp.data["access"] = str(refresh.access_token)
        return resp

    @action(detail=False, methods=["POST"])
    def verify(self, uid, token):
        user = User.objects.get(pk=urlsafe_base64_decode(uid))
        verified = PasswordResetTokenGenerator().check_token(user, token)
        if verified:
            user.is_active = True
            user.save()
            return Response({"message": "Email verified successfully."}, status=200)
        return Response({"message": "Invalid token."}, status=400)


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id).select_related("profile")


class ProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProfileSerializer
    queryset = Profile.objects.all()

    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user).select_related("user")

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        profile_data = {}
        user_data = {}

        updated_user = {}

        for key, value in request.data.items():
            if key in ProfileSerializer.Meta.fields:
                profile_data[key] = value
            else:
                user_data[key] = value

        profile_serializer = ProfileSerializer(instance, data=profile_data, partial=True)
        profile_serializer.is_valid(raise_exception=True)
        updated_profile = profile_serializer.save()

        if user_data:
            user_serializer = UserSerializer(instance.user, data=user_data, partial=True)
            user_serializer.is_valid(raise_exception=True)
            updated_user = user_serializer.save()

        response_data = {
            "first_name": updated_user.first_name,
            "middle_name": updated_user.middle_name,
            "last_name": updated_user.last_name,
            "email": updated_user.email,
            "phone_number": str(updated_user.phone_number),
            "country": str(updated_profile.country.country_code),
            "subdivision": updated_profile.subdivision.code,
            "postal_code": updated_profile.postal_code,
            "preferred_language": updated_profile.preferred_language.code,
            "notify_marketing": updated_profile.notify_marketing,
            "notify_system": updated_profile.notify_system,
        }
        return Response(response_data)
