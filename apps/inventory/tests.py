import datetime
import json
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase
from mongoengine.errors import DoesNotExist, ValidationError

from apps.inventory.views import inventory_to_dict


class InventoryViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def _product(self, product_id="product-1", sku="SKU-001"):
        product = MagicMock()
        product.id = product_id
        product.sku = sku
        return product

    def _storage_location(self, location_id="location-1"):
        storage_location = MagicMock()
        storage_location.id = location_id
        return storage_location

    def _inventory_item(
        self,
        item_id="inventory-1",
        product=None,
        storage_location=None,
        quantity=10,
        reserved=2,
        last_movement_at=None,
    ):
        item = MagicMock()
        item.id = item_id
        item.product = product or self._product()
        item.storage_location = storage_location or self._storage_location()
        item.quantity = quantity
        item.reserved = reserved
        item.last_movement_at = last_movement_at
        return item

    # ==========================================
    #      Тест 1: Перевіряємо легку серіалізацію товару, локації та руху.
    # ==========================================

    def test_inventory_to_dict_serializes_related_fields(self):
        movement_at = datetime.datetime(2026, 5, 9, 12, 30, 0)
        item = self._inventory_item(last_movement_at=movement_at)

        data = inventory_to_dict(item)

        self.assertEqual(data["id"], "inventory-1")
        self.assertEqual(data["product_id"], "product-1")
        self.assertEqual(data["product_sku"], "SKU-001")
        self.assertEqual(data["storage_location_id"], "location-1")
        self.assertEqual(data["quantity"], 10)
        self.assertEqual(data["reserved"], 2)
        self.assertEqual(data["last_movement_at"], movement_at.isoformat())


    # ==========================================
    #      Тест 2: Дивимось, що список інвентарю повертається масивом.
    # ==========================================

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_list_get_returns_all_items(self, mock_inventory_objects):
        mock_inventory_objects.all.return_value = [
            self._inventory_item(item_id="inventory-1", quantity=12),
            self._inventory_item(item_id="inventory-2", quantity=5, reserved=0),
        ]

        response = self.client.get("/inventory")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], "inventory-1")
        self.assertEqual(data[1]["quantity"], 5)

    
    # ==========================================
    #      Тест 3: Створюємо запис через SKU, щоб не вимагати product_id.
    # ==========================================
    
    @patch("apps.inventory.views.StorageLocation.objects")
    @patch("apps.inventory.views.Product.objects")
    @patch("apps.inventory.views.Inventory")
    def test_inventory_post_creates_item_by_product_sku(
        self,
        mock_inventory_class,
        mock_product_objects,
        mock_storage_objects,
    ):
        product = self._product()
        storage_location = self._storage_location()
        created_item = self._inventory_item(
            product=product,
            storage_location=storage_location,
            quantity=25,
            reserved=3,
        )
        mock_product_objects.get.return_value = product
        mock_storage_objects.get.return_value = storage_location
        mock_inventory_class.return_value = created_item

        response = self.client.post(
            "/inventory",
            data=json.dumps(
                {
                    "product_sku": "SKU-001",
                    "storage_location_id": "location-1",
                    "quantity": 25,
                    "reserved": 3,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["quantity"], 25)
        self.assertEqual(response.json()["reserved"], 3)
        mock_product_objects.get.assert_called_once_with(sku="SKU-001")
        mock_storage_objects.get.assert_called_once_with(id="location-1")
        mock_inventory_class.assert_called_once_with(
            product=product,
            storage_location=storage_location,
            quantity=25,
            reserved=3,
        )
        created_item.save.assert_called_once()


    # ==========================================
    #      Тест 4: Невалідний JSON має повертати зрозумілу помилку.
    # ==========================================

    def test_inventory_post_rejects_invalid_json(self):
        response = self.client.post(
            "/inventory",
            data="not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON")


    # ==========================================
    #      Тест 5: Кількість є обов'язковою для нового запису.
    # ==========================================

    def test_inventory_post_requires_quantity(self):
        response = self.client.post(
            "/inventory",
            data=json.dumps(
                {
                    "product_sku": "SKU-001",
                    "storage_location_id": "location-1",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Field 'quantity' is required")


    # ==========================================
    #      Тест 6: Без SKU або id товару запис створити не можна.
    # ==========================================

    def test_inventory_post_requires_product_identifier(self):
        response = self.client.post(
            "/inventory",
            data=json.dumps(
                {
                    "storage_location_id": "location-1",
                    "quantity": 10,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "Either 'product_id' or 'product_sku' is required",
        )


    # ==========================================
    #      Тест 7: Якщо товар не знайдено, віддаємо 404.
    # ==========================================

    @patch("apps.inventory.views.Product.objects")
    def test_inventory_post_returns_404_for_missing_product(self, mock_product_objects):
        mock_product_objects.get.side_effect = DoesNotExist("Product not found")

        response = self.client.post(
            "/inventory",
            data=json.dumps(
                {
                    "product_sku": "BAD-SKU",
                    "storage_location_id": "location-1",
                    "quantity": 10,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "Product not found")

    
    # ==========================================
    #      Тест 8: Якщо локації нема, запис не створюється.
    # ==========================================
    
    @patch("apps.inventory.views.StorageLocation.objects")
    @patch("apps.inventory.views.Product.objects")
    def test_inventory_post_returns_404_for_missing_location(
        self,
        mock_product_objects,
        mock_storage_objects,
    ):
        mock_product_objects.get.return_value = self._product()
        mock_storage_objects.get.side_effect = DoesNotExist("Location not found")

        response = self.client.post(
            "/inventory",
            data=json.dumps(
                {
                    "product_sku": "SKU-001",
                    "storage_location_id": "bad-location",
                    "quantity": 10,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "StorageLocation not found")


    # ==========================================
    #      Тест 9: Помилку валідації зберігання повертаємо як 400.
    # ==========================================

    @patch("apps.inventory.views.StorageLocation.objects")
    @patch("apps.inventory.views.Product.objects")
    @patch("apps.inventory.views.Inventory")
    def test_inventory_post_returns_validation_error(
        self,
        mock_inventory_class,
        mock_product_objects,
        mock_storage_objects,
    ):
        created_item = self._inventory_item(quantity=-1)
        created_item.save.side_effect = ValidationError("Bad inventory data")
        mock_product_objects.get.return_value = self._product()
        mock_storage_objects.get.return_value = self._storage_location()
        mock_inventory_class.return_value = created_item

        response = self.client.post(
            "/inventory",
            data=json.dumps(
                {
                    "product_id": "product-1",
                    "storage_location_id": "location-1",
                    "quantity": -1,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Bad inventory data", response.json()["error"])


    # ==========================================
    #      Тест 10: Детальна сторінка повертає один запис інвентарю.
    # ==========================================

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_detail_get_returns_item(self, mock_inventory_objects):
        mock_inventory_objects.get.return_value = self._inventory_item()

        response = self.client.get("/inventory/inventory-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "inventory-1")


    # ==========================================
    #      Тест 11: Нема запису - повертаємо простий 404.
    # ==========================================

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_detail_returns_404_when_missing(self, mock_inventory_objects):
        mock_inventory_objects.get.side_effect = DoesNotExist("Inventory not found")

        response = self.client.get("/inventory/missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "Inventory not found")


    # ==========================================
    #      Тест 12: PATCH міняє тільки дозволені поля кількості.
    # ==========================================

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_detail_patch_updates_quantity_and_reserved(
        self,
        mock_inventory_objects,
    ):
        item = self._inventory_item(quantity=10, reserved=2)
        mock_inventory_objects.get.return_value = item

        response = self.client.patch(
            "/inventory/inventory-1",
            data=json.dumps(
                {
                    "quantity": 7,
                    "reserved": 1,
                    "product_sku": "IGNORED-SKU",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(item.quantity, 7)
        self.assertEqual(item.reserved, 1)
        self.assertEqual(response.json()["quantity"], 7)
        item.save.assert_called_once()


    # ==========================================
    #      Тест 13: PATCH теж має ловити битий JSON.
    # ==========================================

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_detail_patch_rejects_invalid_json(self, mock_inventory_objects):
        mock_inventory_objects.get.return_value = self._inventory_item()

        response = self.client.patch(
            "/inventory/inventory-1",
            data="{broken",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON")


    # ==========================================
    #      Тест 14: Видалення викликає delete у знайденого запису.
    # ==========================================

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_detail_delete_removes_item(self, mock_inventory_objects):
        item = self._inventory_item()
        mock_inventory_objects.get.return_value = item

        response = self.client.delete("/inventory/inventory-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Inventory deleted")
        item.delete.assert_called_once()
