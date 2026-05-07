from django.test import TestCase, Client
# import json
# from apps.products.models import Product

# class ProductTests(TestCase):

#     def setUp(self):
#         self.client = Client()
#         Product.objects.delete()  #  

#     def test_create_product_success(self):
#         response = self.client.post(
#             "/products",
#             data=json.dumps({
#                 "sku": "TEST-001",
#                 "name": "Test Product",
#                 "manufacturer": "Test",
#                 "form": "Tablet",
#                 "dosage": "500 mg",
#                 "package_size": 10
#             }),
#             content_type="application/json"
#         )

#         print("RESPONSE:", response.json())

#         self.assertEqual(response.status_code, 200)

#     def test_create_product_without_sku(self):
#         response = self.client.post(
#             "/products",
#             data=json.dumps({
#                 "name": "No SKU"
#             }),
#             content_type="application/json"
#         )

#         self.assertEqual(response.status_code, 400)