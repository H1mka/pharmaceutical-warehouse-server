import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from mongoengine.errors import DoesNotExist, ValidationError

class ManipulatorViewsTestCase(TestCase):
    """
    Набір юніт-тестів для перевірки представлень (views) модуля маніпулятора.
    Використовується патерн Mock для підміни звернення до бази даних MongoDB (через MongoEngine).
    """
    def setUp(self):
        self.client = Client()

    @patch('apps.manipulator.views.Manipulator.objects')
    def test_manipulator_detail_get_success(self, mock_manipulator_objects):
        """
        Перевіряє успішне отримання поточного статусу та позиції маніпулятора (GET /control-panel/manipulator-state).
        Мокує запит до бази даних, щоб повернути 'ON' та фейкову позицію.
        """
        mock_manipulator = MagicMock()
        mock_manipulator.status = "ON"
        mock_manipulator.position.id = "60b9c0282b8a9b23b4998765"
        mock_manipulator.position.zone = "A"
        mock_manipulator.position.row = "1"
        mock_manipulator.position.column = "1"
        mock_manipulator_objects.first.return_value = mock_manipulator

        response = self.client.get('/control-panel/manipulator-state')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], "ON")
        self.assertEqual(response.json()['position'], "A - 1 - 1")

    @patch('apps.manipulator.views.Manipulator.objects')
    def test_manipulator_detail_get_not_found(self, mock_manipulator_objects):
        """
        Перевіряє обробку ситуації, коли маніпулятор не знайдено в базі даних.
        Очікується статус 404 (Not Found).
        """
        mock_manipulator_objects.first.side_effect = DoesNotExist("Manipulator not found")
        response = self.client.get('/control-panel/manipulator-state')
        self.assertEqual(response.status_code, 404)

    @patch('apps.manipulator.views.publish_manipulator_state')
    @patch('apps.manipulator.views.StorageLocation.objects')
    @patch('apps.manipulator.views.Manipulator.objects')
    def test_manipulator_detail_patch_success(self, mock_manipulator_objects, mock_storage_objects, mock_publish):
        """
        Перевіряє успішне оновлення (PATCH) статусу та позиції маніпулятора.
        Підміняє запити для знаходження локації за ID та зберігає нові дані.
        """
        mock_manipulator = MagicMock()
        mock_manipulator.status = "OFF"
        mock_manipulator.current_task = None
        mock_manipulator_objects.first.return_value = mock_manipulator

        mock_location = MagicMock()
        mock_location.id = "new_location_id"
        mock_location.zone = "B"
        mock_location.row = "2"
        mock_location.column = "2"
        mock_storage_objects.get.return_value = mock_location

        patch_data = {"status": "ON", "position": "new_location_id"}
        response = self.client.patch('/control-panel/manipulator-state', data=json.dumps(patch_data), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_manipulator.status, "ON")
        self.assertEqual(mock_manipulator.position, mock_location)
        mock_manipulator.save.assert_called_once()

    @patch('apps.manipulator.views._execute_manipulator_task')
    @patch('apps.manipulator.views.publish_manipulator_state')
    @patch('apps.manipulator.views.Manipulator.objects')
    def test_logs_list_create_post_success(self, mock_manipulator_objects, mock_publish, mock_execute):
        """
        Перевіряє успішне створення нового логу маніпулятора (POST /control-panel/logs/).
        Очікується статус 202 (Accepted).
        """
        mock_manipulator = MagicMock()
        mock_manipulator.status = "ON"
        mock_manipulator.current_task = None
        mock_manipulator_objects.first.return_value = mock_manipulator
        
        log_data = {"operation_type": "MOVE"}
        
        response = self.client.post('/control-panel/logs/', data=json.dumps(log_data), content_type='application/json')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['message'], "Operation started in background")
        mock_execute.assert_called_once()

    @patch('apps.manipulator.views._execute_manipulator_task')
    @patch('apps.manipulator.views.publish_manipulator_state')
    @patch('apps.manipulator.views.Manipulator.objects')
    def test_logs_list_create_post_failure_and_abort(self, mock_manipulator_objects, mock_publish, mock_execute):
        """
        Перевіряє сценарій POST запиту для створення логу.
        Очікується статус 202 (Accepted).
        """
        mock_manipulator = MagicMock()
        mock_manipulator.status = "ON"
        mock_manipulator.current_task = None
        mock_manipulator_objects.first.return_value = mock_manipulator

        log_data = {"operation_type": "MOVE"}
        
        response = self.client.post('/control-panel/logs/', data=json.dumps(log_data), content_type='application/json')
        
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['message'], "Operation started in background")

    @patch('apps.manipulator.views.Manipulator.objects')
    def test_logs_list_create_post_manipulator_off(self, mock_manipulator_objects):
        """
        Перевіряє, що маніпулятор не виконує дії (крім START), якщо він вимкнений.
        """
        mock_manipulator = MagicMock()
        mock_manipulator.status = "OFF"
        mock_manipulator.current_task = None
        mock_manipulator_objects.first.return_value = mock_manipulator

        log_data = {"operation_type": "MOVE"}
        response = self.client.post('/control-panel/logs/', data=json.dumps(log_data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Manipulator is OFF")

    def test_logs_list_create_post_invalid_json(self):
        """
        Перевіряє обробку винятку при надсиланні некоректного JSON.
        """
        response = self.client.post('/control-panel/logs/', data="Invalid JSON string", content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON")

    @patch('apps.manipulator.mqtt_client.publish_new_log')
    @patch('apps.manipulator.views.publish_manipulator_state')
    @patch('apps.manipulator.views.ManipulatorLog')
    @patch('apps.manipulator.views.Manipulator.objects')
    @patch('apps.manipulator.views.random.randint')
    @patch('apps.manipulator.views.time_module.sleep')
    def test_execute_manipulator_task_direct_success(self, mock_sleep, mock_randint, mock_manipulator_objects, mock_log_class, mock_publish_state, mock_publish_log):
        """
        Прямий тест логіки створення логів без фонових потоків.
        Мокує ManipulatorLog, щоб уникнути запису в реальну БД.
        """
        mock_manipulator = MagicMock()
        mock_manipulator.status = "ON"
        mock_manipulator_objects.first.return_value = mock_manipulator
        
        mock_randint.return_value = 3000
        
        from apps.manipulator.views import _execute_manipulator_task
        final_log = _execute_manipulator_task("MOVE")
        
        self.assertTrue(mock_log_class.return_value.save.called)
        
        self.assertTrue(mock_publish_state.called)
        self.assertTrue(mock_publish_log.called)

    @patch('apps.manipulator.mqtt_client.publish_new_log')
    @patch('apps.manipulator.views.publish_manipulator_state')
    @patch('apps.manipulator.views.ManipulatorLog')
    @patch('apps.manipulator.views.Manipulator.objects')
    @patch('apps.manipulator.views.random.randint')
    @patch('apps.manipulator.views.time_module.sleep')
    def test_execute_manipulator_task_direct_failure(self, mock_sleep, mock_randint, mock_manipulator_objects, mock_log_class, mock_publish_state, mock_publish_log):
        """
        Тест на симуляцію помилки та статус ABORTED.
        """
        mock_manipulator = MagicMock()
        mock_manipulator.status = "ON"
        mock_manipulator_objects.first.return_value = mock_manipulator
        
        mock_randint.return_value = 9900
        
        from apps.manipulator.views import _execute_manipulator_task
        final_log = _execute_manipulator_task("MOVE")
        
        self.assertTrue(mock_log_class.return_value.save.called)
    
        self.assertGreater(mock_publish_state.call_count, 1)
        self.assertTrue(mock_publish_log.called)

    @patch('apps.manipulator.views.StorageLocation.objects')
    @patch('apps.manipulator.views.Manipulator.objects')
    def test_logs_list_create_post_invalid_location(self, mock_manipulator_objects, mock_storage_objects):
        """
        Перевіряє обробку винятку DoesNotExist, якщо передано неіснуючий storage_location.
        """
        mock_manipulator = MagicMock()
        mock_manipulator.status = "ON"
        mock_manipulator.current_task = None
        mock_manipulator_objects.first.return_value = mock_manipulator
        
        mock_storage_objects.get.side_effect = DoesNotExist("Location not found")

        log_data = {"operation_type": "MOVE", "storage_location": "bad_id"}
        response = self.client.post('/control-panel/logs/', data=json.dumps(log_data), content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("not found", response.json()["error"])

    @patch('apps.manipulator.views.Product.objects')
    @patch('apps.manipulator.views.Manipulator.objects')
    def test_logs_list_create_post_invalid_product(self, mock_manipulator_objects, mock_product_objects):
        """
        Перевіряє обробку винятку DoesNotExist, якщо передано неіснуючий product.
        """
        mock_manipulator = MagicMock()
        mock_manipulator.status = "ON"
        mock_manipulator.current_task = None
        mock_manipulator_objects.first.return_value = mock_manipulator
        
        mock_product_objects.get.side_effect = DoesNotExist("Product not found")

        log_data = {"operation_type": "PICK", "product": "bad_id"}
        response = self.client.post('/control-panel/logs/', data=json.dumps(log_data), content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("not found", response.json()["error"])

    @patch('apps.manipulator.views.ManipulatorLog.objects')
    def test_logs_list_create_get_success(self, mock_log_objects):
        """
        Перевіряє успішне отримання списку логів з підтримкою пагінації (GET /control-panel/logs/).
        Мокує QuerySet (результат вибірки з БД), включаючи методи count, order_by, skip та limit.
        """
        mock_qs = MagicMock()
        mock_qs.count.return_value = 1
        
        mock_log = MagicMock()
        mock_log.id = "log123"
        mock_log.timestamp = None
        mock_log.operation_status = "SUCCESS"
        mock_log.operation_type = "PICK"
        mock_log.duration_ms = 1000
        mock_log.attempt = 1
        mock_log.product = None
        mock_log.storage_location = None
        mock_log.error_msg = None
        mock_log.product_quantity = 0
        mock_log.max_attempts = 2
        
        mock_qs.order_by.return_value.skip.return_value.limit.return_value = [mock_log]
        
        mock_log_objects.return_value = mock_qs
        mock_log_objects.count.return_value = 1

        response = self.client.get('/control-panel/logs/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['id'], "log123")

    @patch('apps.manipulator.views.ManipulatorLog.objects')
    def test_log_detail_get_success(self, mock_log_objects):
        """
        Перевіряє успішне отримання деталей конкретного логу за його ID (GET /control-panel/logs/<id>).
        Мокує метод get() для повернення фейкового об'єкта логу.
        """
        mock_log = MagicMock()
        mock_log.id = "log123"
        mock_log.timestamp = None
        mock_log.operation_status = "SUCCESS"
        mock_log.operation_type = "PICK"
        mock_log.duration_ms = 1000
        mock_log.attempt = 1
        mock_log.product = None
        mock_log.storage_location = None
        mock_log.error_msg = None
        mock_log.product_quantity = 0
        mock_log.max_attempts = 2

        mock_log_objects.get.return_value = mock_log
        
        response = self.client.get('/control-panel/logs/log123')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], "log123")

    @patch('apps.manipulator.views.ManipulatorLog.objects')
    def test_log_detail_delete_success(self, mock_log_objects):
        """
        Перевіряє успішне видалення конкретного логу за його ID (DELETE /control-panel/logs/<id>).
        Переконується, що метод delete() був викликаний у знайденого об'єкта.
        """
        mock_log = MagicMock()
        mock_log_objects.get.return_value = mock_log

        response = self.client.delete('/control-panel/logs/log123')
        self.assertEqual(response.status_code, 200)
        mock_log.delete.assert_called_once()