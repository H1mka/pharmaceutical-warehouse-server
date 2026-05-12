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

    # =========================
    # 1.Перевіряє успішну реєстрацію нового користувача з коректними даними.
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

    # =========================
    # 2.Перевіряє, що система не дозволяє зареєструвати користувача з уже існуючим username.
    # =========================
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

    # =========================
    # 3.Перевіряє обробку помилки, якщо під час реєстрації не передано обов’язкове поле username.
    # =========================
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
    # 4. Перевіряє обробку помилки, якщо під час реєстрації
    # не передано обов’язкове поле password.
    # =========================
    def test_register_no_password(self):
        response = self.client.post(
            "/auth/register",
            data=json.dumps({
                "username": "testuser",
                "role": "admin",
                "first_name": "John",
                "last_name": "Doe"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        
    # =========================
    # 5. Перевіряє обробку помилки, якщо під час реєстрації
    # не передано обов’язкове поле first_name.
    # =========================
    def test_register_no_first_name(self):
        response = self.client.post(
            "/auth/register",
            data=json.dumps({
                "username": "testuser",
                "password": "123456",
                "role": "admin",
                "last_name": "Doe"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # =========================
    # 6. Перевіряє обробку помилки, якщо під час реєстрації
    # не передано обов’язкове поле last_name.
    # =========================
    def test_register_no_last_name(self):
        response = self.client.post(
            "/auth/register",
            data=json.dumps({
                "username": "testuser",
                "password": "123456",
                "role": "admin",
                "first_name": "John"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)


    # =========================
    # 7. Перевіряє обробку некоректного JSON-запиту під час реєстрації.
    # =========================
    def test_register_invalid_json(self):
        response = self.client.post(
            "/auth/register",
            data="invalid json",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        
    # =========================
    # 8. Перевіряє використання неправильного HTTP-методу GET
    # для endpoint реєстрації.
    # =========================
    def test_register_wrong_method_get(self):
        response = self.client.get("/auth/register")

        self.assertEqual(response.status_code, 405)

    # =========================
    # LOGIN
    # =========================
    
    # =========================
    # 9.Перевіряє успішний вхід користувача з коректними даними.
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
    # =========================
    # 10.Перевіряє, що система не дозволяє увійти з неправильним паролем.
    # =========================
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

# =========================
    # 11. Перевіряє, що система не дозволяє увійти з неіснуючим username.
    # =========================
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

    # =========================
    # 12. Перевіряє обробку некоректного JSON-запиту під час авторизації.
    # =========================
    def test_login_invalid_json(self):
        response = self.client.post(
            "/auth/login",
            data="invalid json",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        
    # =========================
    # 13. Перевіряє використання неправильного HTTP-методу GET
    # для endpoint авторизації.
    # =========================
    def test_login_wrong_method_get(self):
        response = self.client.get("/auth/login")

        self.assertEqual(response.status_code, 405)

 # =========================
    # 14. Перевіряє обробку помилки, якщо під час входу
    # не передано username.
    # =========================
    def test_login_no_username(self):
        response = self.client.post(
            "/auth/login",
            data=json.dumps({
                "password": "123456"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # =========================
    # 15. Перевіряє обробку помилки, якщо під час входу
    # не передано password.
    # =========================
    def test_login_no_password(self):
        response = self.client.post(
            "/auth/login",
            data=json.dumps({
                "username": "testuser"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
