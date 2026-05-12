from django.test import TestCase, Client
import json


class QRScannerTests(TestCase):
    def setUp(self):
        self.client = Client()

    # =========================
    # 1. Перевіряє успішне сканування QR-коду з коректними даними
    # та отримання відповіді від сервера.
    # =========================
    def test_qr_scan_with_valid_sku(self):
        response = self.client.post(
            "/api/qr-scan",
            data=json.dumps({"qr_data": "MED-101"}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

    # =========================
    # 2. Перевіряє, що відповідь при успішному скануванні
    # повертається у форматі JSON.
    # =========================
    def test_qr_scan_response_is_json(self):
        response = self.client.post(
            "/api/qr-scan",
            data=json.dumps({"qr_data": "MED-101"}),
            content_type="application/json"
        )

        self.assertEqual(response["Content-Type"], "application/json")

    # =========================
    # 3. Перевіряє, що у відповіді після сканування є хоча б один
    # з очікуваних ключів: product або needs_input.
    # =========================
    def test_qr_scan_response_structure(self):
        response = self.client.post(
            "/api/qr-scan",
            data=json.dumps({"qr_data": "MED-101"}),
            content_type="application/json"
        )

        data = response.json()

        self.assertTrue("product" in data or "needs_input" in data)

    # =========================
    # 4. Перевіряє обробку помилки, якщо під час сканування
    # не передано обов’язкове поле qr_data.
    # =========================
    def test_qr_scan_without_data(self):
        response = self.client.post(
            "/api/qr-scan",
            data=json.dumps({}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # =========================
    # 5. Перевіряє обробку помилки, якщо qr_data передано
    # як порожній рядок.
    # =========================
    def test_qr_scan_empty_qr_data(self):
        response = self.client.post(
            "/api/qr-scan",
            data=json.dumps({"qr_data": ""}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # =========================
    # 6. Перевіряє обробку помилки, якщо qr_data має значення null.
    # =========================
    def test_qr_scan_null_qr_data(self):
        response = self.client.post(
            "/api/qr-scan",
            data=json.dumps({"qr_data": None}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # =========================
    # 7. Перевіряє ситуацію, коли QR-код містить SKU,
    # якого немає в базі даних, і система відкриває форму додавання товару.
    # =========================
    def test_qr_scan_unknown_sku_needs_input(self):
        response = self.client.post(
            "/api/qr-scan",
            data=json.dumps({"qr_data": "invalid_sku"}),
            content_type="application/json"
        )

        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data.get("needs_input"))

    # =========================
    # 8. Перевіряє обробку некоректного JSON-запиту.
    # =========================
    def test_qr_scan_invalid_json(self):
        response = self.client.post(
            "/api/qr-scan",
            data="invalid json",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # =========================
    # 9. Перевіряє використання неправильного HTTP-методу GET
    # для endpoint сканування QR-коду.
    # =========================
    def test_qr_scan_wrong_method_get(self):
        response = self.client.get("/api/qr-scan")

        self.assertEqual(response.status_code, 405)

    # =========================
    # 10. Перевіряє використання неправильного HTTP-методу PUT
    # для endpoint сканування QR-коду.
    # =========================
    def test_qr_scan_wrong_method_put(self):
        response = self.client.put(
            "/api/qr-scan",
            data=json.dumps({"qr_data": "MED-101"}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 405)