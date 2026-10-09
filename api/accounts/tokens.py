from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Token for the emailed verification link. Mixing ``is_verified`` into the
    hash makes the link single-use: verifying the account flips the flag, so the
    same token no longer checks out (the stock generator only changes with the
    password or last login, neither of which verification touches)."""

    def _make_hash_value(self, user, timestamp):
        return f"{super()._make_hash_value(user, timestamp)}{user.is_verified}"


email_verification_token = EmailVerificationTokenGenerator()
