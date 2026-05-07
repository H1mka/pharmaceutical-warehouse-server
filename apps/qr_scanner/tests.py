
from django.test import TestCase, Client
import json

class QRScannerTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_qr_scan_with_valid_sku(self):
        response = self.client.post(
            "/api/qr-scan",
            data=json.dumps({"qr_data": "MED-101"}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

    def test_qr_scan_without_data(self):
        response = self.client.post(
            "/api/qr-scan",
            data=json.dumps({}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_qr_scan_wrong_method(self):
        response = self.client.get("/api/qr-scan")
        self.assertEqual(response.status_code, 405)