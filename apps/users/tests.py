from django.test import TestCase, Client
import json
from apps.users.models import User


class UserTests(TestCase):

    def setUp(self):
        self.client = Client()
        User.objects.delete()

    # =========================
    # REGISTER
    # =========================

    def test_register_success(self):
        response = self.client.post(
            "/auth/register",
            data=json.dumps({
                "username": "testuser",
                "password": "123456",
                "role": "admin",
                "first_name": "John",
                "last_name": "Doe"
            }),
            content_type="application/json"
        )

        print("REGISTER RESPONSE:", response.json())

        self.assertEqual(response.status_code, 201)

    def test_register_duplicate(self):
        # first register
        self.client.post(
            "/auth/register",
            data=json.dumps({
                "username": "testuser",
                "password": "123456",
                "role": "admin",
                "first_name": "John",
                "last_name": "Doe"
            }),
            content_type="application/json"
        )

        # duplicate register
        response = self.client.post(
            "/auth/register",
            data=json.dumps({
                "username": "testuser",
                "password": "123456",
                "role": "admin",
                "first_name": "John",
                "last_name": "Doe"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_register_no_username(self):
        response = self.client.post(
            "/auth/register",
            data=json.dumps({
                "password": "123456",
                "role": "admin",
                "first_name": "John",
                "last_name": "Doe"
            }),
            content_type="application/json"
        )

        print("NO USERNAME RESPONSE:", response.json())

        self.assertEqual(response.status_code, 400)

    # =========================
    # LOGIN
    # =========================

    def test_login_success(self):

        # register first
        self.client.post(
            "/auth/register",
            data=json.dumps({
                "username": "testuser",
                "password": "123456",
                "role": "admin",
                "first_name": "John",
                "last_name": "Doe"
            }),
            content_type="application/json"
        )

        # login
        response = self.client.post(
            "/auth/login",
            data=json.dumps({
                "username": "testuser",
                "password": "123456"
            }),
            content_type="application/json"
        )

        print("LOGIN RESPONSE:", response.json())

        self.assertEqual(response.status_code, 200)

    def test_login_wrong_password(self):

        self.client.post(
            "/auth/register",
            data=json.dumps({
                "username": "testuser",
                "password": "123456",
                "role": "admin",
                "first_name": "John",
                "last_name": "Doe"
            }),
            content_type="application/json"
        )

        response = self.client.post(
            "/auth/login",
            data=json.dumps({
                "login": "testuser",
                "password": "wrong"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_login_user_not_found(self):
        response = self.client.post(
            "/auth/login",
            data=json.dumps({
                "login": "ghost",
                "password": "123456"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_login_invalid_json(self):
        response = self.client.post(
            "/auth/login",
            data="invalid json",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)