import json
import datetime
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client

class OperationLogsAnalyticsTestCase(TestCase):
    """
    Набір юніт-тестів для перевірки представлень (views) модуля operation_logs.
    Тестуємо генерацію аналітики та обробку різних винятків.
    """
    def setUp(self):
        self.client = Client()

    def _create_mock_log(self, date_str, qty, duration_ms):
        log = MagicMock()
        log.created_at = datetime.datetime.fromisoformat(date_str)
        log.product_quantity = qty
        log.message = None
        
        log.product.id = "prod123"
        log.product.sku = "SKU-123"
        log.product.name = "Test Product"
        
        log.manipulator_task = MagicMock()
        log.manipulator_task.duration_ms = duration_ms
        log.manipulator_task.product_quantity = qty
        return log

    @patch('apps.operation_logs.views.OperationLogs.objects')
    def test_dispense_load_analytics_success(self, mock_objects):
        """
        Перевіряє успішну генерацію аналітики для двох записів.
        """
        mock_qs = MagicMock()
        log1 = self._create_mock_log("2026-05-01T10:00:00", 10, 5000)
        log2 = self._create_mock_log("2026-05-01T11:30:00", 20, 6000)
        
        # Мокуємо виклик order_by(), який має повернути список логів
        mock_qs.order_by.return_value = [log1, log2]
        mock_objects.return_value = mock_qs

        response = self.client.get('/analytics/dispense-load?granularity=day')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['summary']['dispense_count'], 2)
        self.assertEqual(data['summary']['total_quantity'], 30)
        self.assertEqual(data['summary']['total_duration_ms'], 11000)

    @patch('apps.operation_logs.views.OperationLogs.objects')
    def test_dispense_load_analytics_empty(self, mock_objects):
        """
        Перевіряє коректну відповідь, якщо логів у базі немає.
        """
        mock_qs = MagicMock()
        mock_qs.order_by.return_value = []
        mock_objects.return_value = mock_qs

        response = self.client.get('/analytics/dispense-load')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['summary']['dispense_count'], 0)
        self.assertEqual(data['series']['total'], [])

    def test_dispense_load_analytics_invalid_method(self):
        """
        Перевіряє, що метод POST не дозволяється для цього endpoint-у.
        """
        response = self.client.post('/analytics/dispense-load')
        self.assertEqual(response.status_code, 405)  # Method Not Allowed

    def test_dispense_load_analytics_invalid_granularity(self):
        """
        Перевіряє обробку помилки при передачі невідомої granularity (наприклад, decade).
        """
        response = self.client.get('/analytics/dispense-load?granularity=decade')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid granularity", response.json()["error"])

    def test_dispense_load_analytics_invalid_date_format(self):
        """
        Перевіряє перевірку некоректного формату дати в параметрах from / to.
        """
        response = self.client.get('/analytics/dispense-load?from=bad_date')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid 'from' format", response.json()["error"])

    def test_dispense_load_analytics_date_range_error(self):
        """
        Перевіряє помилку, коли start_date пізніше за end_date.
        """
        response = self.client.get('/analytics/dispense-load?from=2026-05-10&to=2026-05-01')
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be later than", response.json()["error"])
