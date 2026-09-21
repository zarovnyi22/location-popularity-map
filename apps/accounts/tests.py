from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase


class RegistrationLoginTests(APITestCase):
    def test_register_creates_user(self):
        url = reverse("auth-register")
        response = self.client.post(
            url,
            {"username": "nazar", "email": "nazar@example.com", "password": "S0meStrongPass!"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="nazar").exists())
        # Registering does not log the user in.
        self.assertFalse("_auth_user_id" in self.client.session)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user("existing", email="taken@example.com", password="pw12345678")
        response = self.client.post(
            reverse("auth-register"),
            {"username": "other", "email": "taken@example.com", "password": "S0meStrongPass!"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_sets_session_cookie(self):
        User.objects.create_user("nazar", password="S0meStrongPass!")
        response = self.client.post(reverse("auth-login"), {"username": "nazar", "password": "S0meStrongPass!"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sessionid", response.cookies)

    def test_login_wrong_password(self):
        User.objects.create_user("nazar", password="S0meStrongPass!")
        response = self.client.post(reverse("auth-login"), {"username": "nazar", "password": "wrong"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_requires_auth_and_clears_session(self):
        user = User.objects.create_user("nazar", password="S0meStrongPass!")
        self.client.force_login(user)
        response = self.client.post(reverse("auth-logout"))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse("_auth_user_id" in self.client.session)


class PasswordResetTests(APITestCase):
    def test_reset_flow_end_to_end(self):
        user = User.objects.create_user("nazar", email="nazar@example.com", password="OldPassword1")

        response = self.client.post(reverse("auth-password-reset"), {"email": "nazar@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {"uid": uid, "token": token, "new_password": "BrandNewPassword1"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.check_password("BrandNewPassword1"))

    def test_reset_unknown_email_still_returns_200(self):
        response = self.client.post(reverse("auth-password-reset"), {"email": "nobody@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_confirm_rejects_bad_token(self):
        User.objects.create_user("nazar", email="nazar@example.com", password="OldPassword1")
        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {"uid": "bad", "token": "bad", "new_password": "BrandNewPassword1"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
