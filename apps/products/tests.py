import datetime
import json
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase
from mongoengine.errors import DoesNotExist, ValidationError

from apps.products.views import product_to_dict


class ProductsViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def _product(
        self,
        product_id="product-1",
        sku="SKU-001",
        name="Aspirin",
        manufacturer="Pharma Inc",
        form="tablet",
        dosage="500mg",
        package_size=20,
        expiration_date=None,
        created_at=None,
        updated_at=None,
    ):
        product = MagicMock()
        product.id = product_id
        product.sku = sku
        product.name = name
        product.manufacturer = manufacturer
        product.form = form
        product.dosage = dosage
        product.package_size = package_size
        product.expiration_date = expiration_date
        product.created_at = created_at or datetime.datetime(2026, 5, 1, 10, 0, 0)
        product.updated_at = updated_at or datetime.datetime(2026, 5, 2, 11, 0, 0)
        return product

    def _location(self, location_id="location-1", zone="A", location_type="STORAGE", is_active=True):
        location = MagicMock()
        location.id = location_id
        location.zone = zone
        location.location_type = location_type
        location.is_active = is_active
        location.capacity = 100
        return location

    def _inventory(self, product=None, quantity=10, storage_location=None):
        inventory = MagicMock()
        inventory.product = product or self._product()
        inventory.quantity = quantity
        inventory.storage_location = storage_location or self._location()
        return inventory


    # ==========================================
    #      Тест 1: Перевіряємо, що товар правильно перетворюється в JSON-словник.
    # ==========================================

    def test_product_to_dict_serializes_dates(self):
        expiration_date = datetime.datetime(2027, 1, 1, 0, 0, 0)
        product = self._product(expiration_date=expiration_date)

        data = product_to_dict(product)

        self.assertEqual(data["id"], "product-1")
        self.assertEqual(data["sku"], "SKU-001")
        self.assertEqual(data["name"], "Aspirin")
        self.assertEqual(data["expiration_date"], expiration_date.isoformat())
        self.assertEqual(data["created_at"], product.created_at.isoformat())
        self.assertEqual(data["updated_at"], product.updated_at.isoformat())


    # ==========================================
    #      Тест 2: Список товарів має додавати кількість зі складських локацій.
    # ==========================================

    @patch("apps.products.views.Inventory.objects")
    @patch("apps.products.views.Product.objects")
    def test_products_list_get_returns_products_with_storage_quantity(
        self,
        mock_product_objects,
        mock_inventory_objects,
    ):
        product = self._product()
        product_qs = MagicMock()
        product_qs.count.return_value = 1
        product_qs.order_by.return_value.skip.return_value.limit.return_value = [product]
        mock_product_objects.all.return_value = product_qs
        mock_inventory_objects.return_value.only.return_value = [
            self._inventory(product=product, quantity=12)
        ]

        response = self.client.get("/products")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"][0]["sku"], "SKU-001")
        self.assertEqual(data["data"][0]["quantity"], 12)
        self.assertIn("extra", data)


    # ==========================================
    #      Тест 3: Некоректна пагінація повертає 400 з повідомленням.
    # ==========================================

    @patch("apps.products.views.generate_pagination")
    @patch("apps.products.views.Product.objects")
    def test_products_list_get_returns_400_for_bad_pagination(
        self,
        mock_product_objects,
        mock_generate_pagination,
    ):
        product_qs = MagicMock()
        product_qs.count.return_value = 1
        mock_product_objects.all.return_value = product_qs
        mock_generate_pagination.side_effect = ValueError("Invalid page")

        response = self.client.get("/products?page=bad")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["error"], "Invalid page")


    # ==========================================
    #      Тест 4: POST створює товар, якщо передані валідні базові поля.
    # ==========================================

    @patch("apps.products.views.Product")
    def test_products_post_creates_product_without_quantity(self, mock_product_class):
        product = self._product()
        product.expiration_date = None
        mock_product_class.return_value = product
        mock_product_class.objects.return_value.first.return_value = None

        response = self.client.post(
            "/products",
            data=json.dumps(
                {
                    "sku": "SKU-001",
                    "name": "Aspirin",
                    "manufacturer": "Pharma Inc",
                    "form": "tablet",
                    "dosage": "500mg",
                    "package_size": 20,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sku"], "SKU-001")
        product.save.assert_called_once()


    # ==========================================
    #      Тест 5: Битий JSON не має проходити далі в логіку створення.
    # ==========================================

    def test_products_post_rejects_invalid_json(self):
        response = self.client.post(
            "/products",
            data="not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON")


    # ==========================================
    #      Тест 6: Дублікат SKU повертає помилку унікальності.
    # ==========================================

    @patch("apps.products.views.Product")
    def test_products_post_rejects_duplicate_sku(self, mock_product_class):
        mock_product_class.return_value = self._product()
        mock_product_class.objects.return_value.first.return_value = self._product()

        response = self.client.post(
            "/products",
            data=json.dumps({"sku": "SKU-001", "name": "Aspirin"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Tried to save duplicate unique sku values")


    # ==========================================
    #      Тест 7: Детальний GET повертає товар за SKU.
    # ==========================================

    @patch("apps.products.views.Product.objects")
    def test_product_detail_get_returns_product(self, mock_product_objects):
        mock_product_objects.get.return_value = self._product()

        response = self.client.get("/products/SKU-001")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sku"], "SKU-001")


    # ==========================================
    #      Тест 8: Якщо товар не знайдено, повертаємо 404.
    # ==========================================

    @patch("apps.products.views.Product.objects")
    def test_product_detail_returns_404_when_missing(self, mock_product_objects):
        mock_product_objects.get.side_effect = DoesNotExist("Product not found")

        response = self.client.get("/products/MISSING")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "Product not found")


    # ==========================================
    #      Тест 9: PATCH відхиляє невалідний JSON.
    # ==========================================

    @patch("apps.products.views.Product.objects")
    def test_product_detail_patch_rejects_invalid_json(self, mock_product_objects):
        mock_product_objects.get.return_value = self._product()

        response = self.client.patch(
            "/products/SKU-001",
            data="{bad",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON")

    
    # ==========================================
    #      Тест 10: DELETE видаляє знайдений товар.
    # ==========================================

    @patch("apps.products.views.Product.objects")
    def test_product_detail_delete_removes_product(self, mock_product_objects):
        product = self._product()
        mock_product_objects.get.return_value = product

        response = self.client.delete("/products/SKU-001")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Product deleted")
        product.delete.assert_called_once()


    # ==========================================
    #      Тест 11: Приймання товару викликає розміщення на складі.
    # ==========================================

    @patch("apps.products.views.allocate_product_quantity")
    @patch("apps.products.views.Product.objects")
    def test_receive_product_adds_quantity(
        self,
        mock_product_objects,
        mock_allocate_product_quantity,
    ):
        product = self._product()
        mock_product_objects.get.return_value = product
        mock_allocate_product_quantity.return_value = (True, "")

        response = self.client.post(
            "/products/SKU-001/receive",
            data=json.dumps({"quantity": 8}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["added_quantity"], 8)
        mock_allocate_product_quantity.assert_called_once_with(product, 8)
        product.save.assert_called_once()


    # ==========================================
    #      Тест 12: Помилка розміщення при прийманні повертається клієнту.
    # ==========================================

    @patch("apps.products.views.allocate_product_quantity")
    @patch("apps.products.views.Product.objects")
    def test_receive_product_returns_allocation_error(
        self,
        mock_product_objects,
        mock_allocate_product_quantity,
    ):
        mock_product_objects.get.return_value = self._product()
        mock_allocate_product_quantity.return_value = (False, "No capacity")

        response = self.client.post(
            "/products/SKU-001/receive",
            data=json.dumps({"quantity": 8}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "No capacity")


    # ==========================================
    #      Тест 13: Видача товару викликає складське списання.
    # ==========================================

    @patch("apps.products.views.dispense_product_quantity")
    @patch("apps.products.views.Product.objects")
    def test_dispense_product_removes_quantity(
        self,
        mock_product_objects,
        mock_dispense_product_quantity,
    ):
        product = self._product()
        mock_product_objects.get.return_value = product
        mock_dispense_product_quantity.return_value = (True, "")

        response = self.client.post(
            "/products/SKU-001/dispense",
            data=json.dumps({"quantity": 4}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["dispensed_quantity"], 4)
        mock_dispense_product_quantity.assert_called_once_with(product, 4)
        product.save.assert_called_once()


    # ==========================================
    #      Тест 14: Видача теж вимагає додатне ціле quantity.
    # ==========================================

    @patch("apps.products.views.Product.objects")
    def test_dispense_product_rejects_invalid_quantity(self, mock_product_objects):
        mock_product_objects.get.return_value = self._product()

        response = self.client.post(
            "/products/SKU-001/dispense",
            data=json.dumps({"quantity": -1}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Field 'quantity' must be a positive integer")


    # ==========================================
    #      Тест 15: Аналітика без логів повертає порожню успішну відповідь.
    # ==========================================

    @patch("apps.products.views.OperationLogs.objects")
    def test_product_popularity_analytics_returns_empty_response(self, mock_log_objects):
        mock_log_objects.return_value.order_by.return_value = []

        response = self.client.get("/analytics/products/popularity?limit=5")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["summary"]["products_count"], 0)
        self.assertEqual(data["items"], [])
        self.assertEqual(data["filters"]["limit"], 5)


    # ==========================================
    #      Тест 16: Аналітика групує DISPENSE-логи за товаром.
    # ==========================================

    @patch("apps.products.views.OperationLogs.objects")
    def test_product_popularity_analytics_groups_logs_by_product(self, mock_log_objects):
        product_a = self._product(product_id="a", sku="A-1", name="Aspirin")
        product_b = self._product(product_id="b", sku="B-1", name="Balm")
        log_1 = MagicMock(product=product_a, product_quantity=5, created_at=datetime.datetime(2026, 5, 1, 9, 0, 0))
        log_2 = MagicMock(product=product_a, product_quantity=3, created_at=datetime.datetime(2026, 5, 2, 9, 0, 0))
        log_3 = MagicMock(product=product_b, product_quantity=10, created_at=datetime.datetime(2026, 5, 3, 9, 0, 0))
        mock_log_objects.return_value.order_by.return_value = [log_1, log_2, log_3]

        response = self.client.get("/analytics/products/popularity?sort_by=quantity&limit=2")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"]["products_count"], 2)
        self.assertEqual(data["summary"]["total_dispensed_quantity"], 18)
        self.assertEqual(data["items"][0]["sku"], "B-1")
        self.assertEqual(data["items"][0]["dispensed_quantity"], 10)
        self.assertEqual(data["items"][1]["sku"], "A-1")
        self.assertEqual(data["items"][1]["dispense_count"], 2)


    # ==========================================
    #      Тест 17: Невідоме сортування для аналітики повертає 400.
    # ==========================================

    def test_product_popularity_analytics_rejects_invalid_sort_by(self):
        response = self.client.get("/analytics/products/popularity?sort_by=bad")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertIn("Invalid sort_by", response.json()["error"])
