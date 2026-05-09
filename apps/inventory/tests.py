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

    def test_inventory_to_dict_serializes_related_fields(self):
        # Перевіряємо легку серіалізацію товару, локації та руху.
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

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_list_get_returns_all_items(self, mock_inventory_objects):
        # Дивимось, що список інвентарю повертається масивом.
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

    @patch("apps.inventory.views.StorageLocation.objects")
    @patch("apps.inventory.views.Product.objects")
    @patch("apps.inventory.views.Inventory")
    def test_inventory_post_creates_item_by_product_sku(
        self,
        mock_inventory_class,
        mock_product_objects,
        mock_storage_objects,
    ):
        # Створюємо запис через SKU, щоб не вимагати product_id.
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

    def test_inventory_post_rejects_invalid_json(self):
        # Невалідний JSON має повертати зрозумілу помилку.
        response = self.client.post(
            "/inventory",
            data="not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON")

    def test_inventory_post_requires_quantity(self):
        # Кількість є обов'язковою для нового запису.
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

    def test_inventory_post_requires_product_identifier(self):
        # Без SKU або id товару запис створити не можна.
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

    @patch("apps.inventory.views.Product.objects")
    def test_inventory_post_returns_404_for_missing_product(self, mock_product_objects):
        # Якщо товар не знайдено, віддаємо 404.
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

    @patch("apps.inventory.views.StorageLocation.objects")
    @patch("apps.inventory.views.Product.objects")
    def test_inventory_post_returns_404_for_missing_location(
        self,
        mock_product_objects,
        mock_storage_objects,
    ):
        # Якщо локації нема, запис не створюється.
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

    @patch("apps.inventory.views.StorageLocation.objects")
    @patch("apps.inventory.views.Product.objects")
    @patch("apps.inventory.views.Inventory")
    def test_inventory_post_returns_validation_error(
        self,
        mock_inventory_class,
        mock_product_objects,
        mock_storage_objects,
    ):
        # Помилку валідації зберігання повертаємо як 400.
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

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_detail_get_returns_item(self, mock_inventory_objects):
        # Детальна сторінка повертає один запис інвентарю.
        mock_inventory_objects.get.return_value = self._inventory_item()

        response = self.client.get("/inventory/inventory-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "inventory-1")

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_detail_returns_404_when_missing(self, mock_inventory_objects):
        # Нема запису - маємо простий 404.
        mock_inventory_objects.get.side_effect = DoesNotExist("Inventory not found")

        response = self.client.get("/inventory/missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "Inventory not found")

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_detail_patch_updates_quantity_and_reserved(
        self,
        mock_inventory_objects,
    ):
        # PATCH міняє тільки дозволені поля кількості.
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

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_detail_patch_rejects_invalid_json(self, mock_inventory_objects):
        # PATCH теж має ловити битий JSON.
        mock_inventory_objects.get.return_value = self._inventory_item()

        response = self.client.patch(
            "/inventory/inventory-1",
            data="{broken",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON")

    @patch("apps.inventory.views.Inventory.objects")
    def test_inventory_detail_delete_removes_item(self, mock_inventory_objects):
        # Видалення викликає delete у знайденого запису.
        item = self._inventory_item()
        mock_inventory_objects.get.return_value = item

        response = self.client.delete("/inventory/inventory-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Inventory deleted")
        item.delete.assert_called_once()
