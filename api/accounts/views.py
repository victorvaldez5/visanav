from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import transaction
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext as _
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
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
        user = User.objects.get(email=resp.data["email"])
        # New accounts are inactive until the user confirms their email via the
        # link in the verification message. SimpleJWT rejects inactive users at
        # login and on every authenticated request, so we issue no session here.
        user.is_active = False
        user.save(update_fields=["is_active"])
        # The registering browser's language (negotiated from Accept-Language by
        # LocaleMiddleware): the new account has no profile language yet.
        send_verification_email(user, locale=request.LANGUAGE_CODE)
        resp.data["detail"] = _("Account created. Check your email to verify your account.")
        return resp


class VerifyEmailView(APIView):
    """Activate an account from the emailed verification link.

    ``send_verification_email`` (core/mail.py) links to the SPA's ``/verify``
    page, which POSTs the base64-encoded user id + token here. On success the
    account is activated and a session is issued, so the user is signed in
    straight away. Bad/expired links are rejected without activating anything.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get("uid") or ""
        token = request.data.get("token") or ""
        try:
            pk = urlsafe_base64_decode(uid).decode()
            user = User.objects.get(pk=pk)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            return Response(
                {"detail": _("Invalid verification link.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not PasswordResetTokenGenerator().check_token(user, token):
            return Response(
                {"detail": _("This verification link is invalid or has expired.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = True
        user.is_verified = True
        user.save(update_fields=["is_active", "is_verified"])

        # Same builder as login, so the token carries the username/email claims the
        # app reads to label the signed-in user (for_user() alone omits them).
        refresh = CustomTokenObtainPairSerializer.get_token(user)
        return Response(
            {
                "userId": user.id,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class AccountErasureView(APIView):
    """Permanently erase the authenticated user and everything they own.

    Deleting the ``User`` cascades to their ``Profile`` and, via the
    ``conversations`` relation, their ``Conversation``/``Message``/``Feedback``
    rows — the GDPR/CCPA "right to delete". The account password is required as
    confirmation of an irreversible action.

    A conversation under a legal hold is preserved: a preservation duty (e.g. a
    subpoena) overrides the erasure right, so if any exist the request is refused
    (409) and nothing is deleted, rather than destroying held data. Anonymous
    conversations aren't owned by an account — they auto-expire and can be
    deleted individually by UUID.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        password = request.data.get("password") or ""
        if not user.check_password(password):
            return Response(
                {"detail": _("Password is incorrect.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        held = user.conversations.filter(legal_hold=True)
        held_count = held.count()
        if held_count:
            return Response(
                {
                    "detail": _(
                        "Some of your conversations are under a legal hold and "
                        "cannot be deleted right now. They will be removed once "
                        "the hold is lifted."
                    ),
                    "held_conversations": held_count,
                },
                status=status.HTTP_409_CONFLICT,
            )

        conversations_deleted = user.conversations.count()
        user.delete()
        return Response(
            {
                "detail": _(
                    "Your account and all associated data have been "
                    "permanently deleted."
                ),
                "conversations_deleted": conversations_deleted,
            },
            status=status.HTTP_200_OK,
        )


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

        for key, value in request.data.items():
            if key in ProfileSerializer.Meta.fields:
                profile_data[key] = value
            else:
                user_data[key] = value

        profile_serializer = ProfileSerializer(instance, data=profile_data, partial=True)
        profile_serializer.is_valid(raise_exception=True)

        user_serializer = None
        if user_data:
            user_serializer = UserSerializer(instance.user, data=user_data, partial=True)
            user_serializer.is_valid(raise_exception=True)

        # Validate both halves before saving either, so a bad user field can't
        # leave the profile half-updated.
        with transaction.atomic():
            profile_serializer.save()
            if user_serializer is not None:
                user_serializer.save()

        # One flat object: the user's fields plus the profile's. Related fields
        # serialize as their codes (country "US", preferred_language "es") and
        # may be null, which a PATCH of a single field (e.g. the language
        # switcher's write-through) must survive.
        return Response({**UserSerializer(instance.user).data, **profile_serializer.data})
