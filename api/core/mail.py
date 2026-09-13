import mailtrap as mt
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from jwt.utils import force_bytes


def send_verification_email(user):
    uid = urlsafe_base64_encode(force_bytes(str(user.pk)))
    token = PasswordResetTokenGenerator().make_token(user)
    url = f"{settings.FRONTEND_URL}/verify?uid={uid}&token={token}"

    client = mt.MailtrapClient(api_host="sandbox.api.mailtrap.io", token=settings.MAILTRAP_API_KEY, sandbox=True,
                               inbox_id="3972833")
    mail = mt.Mail(
        sender=mt.Address(
            email="mailtrap@example.com", name="Mailtrap Verification Test"
        ),
        to=[mt.Address(email=user.email, name=user.email)],
        subject="Verify your account",
        text=f"Hello {user.email}, Thanks for signing up! Please verify your account by clicking on the link below: {url}",
        category="Test",
    )

    client.send(mail)
