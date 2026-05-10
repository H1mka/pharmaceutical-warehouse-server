import datetime
import json
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase
from mongoengine.errors import DoesNotExist, ValidationError

from apps.storage_location.views import storage_location_to_dict


class StorageLocationViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def _storage_location(
        self,
        location_id="location-1",
        zone="A",
        location_type="STORAGE",
        row=1,
        column=2,
        capacity=100,
        is_active=True,
        created_at=None,
    ):
        storage_location = MagicMock()
        storage_location.id = location_id
        storage_location.zone = zone
        storage_location.location_type = location_type
        storage_location.row = row
        storage_location.column = column
        storage_location.capacity = capacity
        storage_location.is_active = is_active
        storage_location.created_at = created_at or datetime.datetime(2026, 5, 10, 9, 0, 0)
        return storage_location


    # ==========================================
    #      Тест 1: Перевіряємо серіалізацію локації в словник.
    # ==========================================

    def test_storage_location_to_dict_serializes_fields(self):
        storage_location = self._storage_location()

        data = storage_location_to_dict(storage_location)

        self.assertEqual(data["id"], "location-1")
        self.assertEqual(data["zone"], "A")
        self.assertEqual(data["location_type"], "STORAGE")
        self.assertEqual(data["row"], 1)
        self.assertEqual(data["column"], 2)
        self.assertEqual(data["capacity"], 100)
        self.assertTrue(data["is_active"])
        self.assertEqual(data["created_at"], storage_location.created_at.isoformat())


    # ==========================================
    #      Тест 2: Список локацій повертається масивом.
    # ==========================================

    @patch("apps.storage_location.views.StorageLocation.objects")
    def test_storage_location_list_get_returns_locations(self, mock_storage_objects):
        mock_storage_objects.all.return_value = [
            self._storage_location(location_id="location-1"),
            self._storage_location(location_id="location-2", zone="B", capacity=50),
        ]

        response = self.client.get("/storage-locations")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], "location-1")
        self.assertEqual(data[1]["zone"], "B")


    # ==========================================
    #      Тест 3: POST створює нову складську локацію.
    # ==========================================

    @patch("apps.storage_location.views.StorageLocation")
    def test_storage_location_post_creates_location(self, mock_storage_class):
        created_location = self._storage_location(
            zone="LOADING",
            location_type="LOADING",
            row=0,
            column=1,
            capacity=25,
        )
        mock_storage_class.return_value = created_location

        response = self.client.post(
            "/storage-locations",
            data=json.dumps(
                {
                    "zone": "LOADING",
                    "location_type": "LOADING",
                    "row": 0,
                    "column": 1,
                    "capacity": 25,
                    "is_active": True,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["zone"], "LOADING")
        self.assertEqual(response.json()["location_type"], "LOADING")
        self.assertEqual(created_location.row, 0)
        self.assertEqual(created_location.capacity, 25)
        created_location.save.assert_called_once()


    # ==========================================
    #      Тест 4: Некоректний JSON повертає 400.
    # ==========================================

    def test_storage_location_post_rejects_invalid_json(self):
        response = self.client.post(
            "/storage-locations",
            data="bad-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON")


    # ==========================================
    #      Тест 5: Якщо локації нема, повертаємо 404.
    # ==========================================

    @patch("apps.storage_location.views.StorageLocation.objects")
    def test_storage_location_detail_returns_404_when_missing(self, mock_storage_objects):
        mock_storage_objects.get.side_effect = DoesNotExist("StorageLocation not found")

        response = self.client.get("/storage-locations/missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "StorageLocation not found")


    # ==========================================
    #      Тест 6: PATCH оновлює поля локації.
    # ==========================================

    @patch("apps.storage_location.views.StorageLocation.objects")
    def test_storage_location_detail_patch_updates_allowed_fields(self, mock_storage_objects):
        # PATCH оновлює поля локації.
        storage_location = self._storage_location()
        mock_storage_objects.get.return_value = storage_location

        response = self.client.patch(
            "/storage-locations/location-1",
            data=json.dumps(
                {
                    "zone": "B",
                    "row": 3,
                    "column": 4,
                    "capacity": 75,
                    "is_active": False,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(storage_location.zone, "B")
        self.assertEqual(storage_location.row, 3)
        self.assertEqual(storage_location.column, 4)
        self.assertEqual(storage_location.capacity, 75)
        self.assertFalse(storage_location.is_active)
        storage_location.save.assert_called_once()


    # ==========================================
    #      Тест 7: DELETE видаляє знайдену локацію.
    # ==========================================

    @patch("apps.storage_location.views.StorageLocation.objects")
    def test_storage_location_detail_delete_removes_location(self, mock_storage_objects):
        # DELETE видаляє знайдену локацію.
        storage_location = self._storage_location()
        mock_storage_objects.get.return_value = storage_location

        response = self.client.delete("/storage-locations/location-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "StorageLocation deleted")
        storage_location.delete.assert_called_once()
