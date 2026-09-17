from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from conversation.models import Conversation, Message

User = get_user_model()
PW = "Sup3r-Secret-Pw!"
ERASE_URL = "/api/auth/erase/"


class AccountErasureTests(APITestCase):
    def _make_user(self, email="a@example.com"):
        return User.objects.create_user(username=email, email=email, password=PW)

    def test_requires_authentication(self):
        resp = self.client.post(ERASE_URL, {"password": PW})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_erases_user_and_owned_data_only(self):
        user = self._make_user()
        conv = Conversation.objects.create(user=user)
        Message.objects.create(
            conversation=conv, parts={"content": "my visa question"}, kind="request"
        )
        other = self._make_user("b@example.com")
        other_conv = Conversation.objects.create(user=other)

        self.client.force_authenticate(user=user)
        resp = self.client.post(ERASE_URL, {"password": PW})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["conversations_deleted"], 1)
        # Requester and everything cascading from them are gone.
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(Conversation.objects.filter(pk=conv.pk).exists())
        self.assertEqual(Message.objects.count(), 0)
        # Another user's data is untouched.
        self.assertTrue(User.objects.filter(pk=other.pk).exists())
        self.assertTrue(Conversation.objects.filter(pk=other_conv.pk).exists())

    def test_wrong_password_deletes_nothing(self):
        user = self._make_user()
        self.client.force_authenticate(user=user)
        resp = self.client.post(ERASE_URL, {"password": "not-the-password"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_missing_password_deletes_nothing(self):
        user = self._make_user()
        self.client.force_authenticate(user=user)
        resp = self.client.post(ERASE_URL, {})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_legal_hold_blocks_erasure(self):
        user = self._make_user()
        Conversation.objects.create(user=user)
        Conversation.objects.create(user=user, legal_hold=True)

        self.client.force_authenticate(user=user)
        resp = self.client.post(ERASE_URL, {"password": PW})

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["held_conversations"], 1)
        # Nothing is deleted while a hold is in place.
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertEqual(Conversation.objects.filter(user=user).count(), 2)
