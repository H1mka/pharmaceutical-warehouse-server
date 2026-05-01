from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse
from apps.products.models import Product
from apps.products.views import allocate_product_quantity


@csrf_exempt
def qr_scan(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        body = json.loads(request.body)
    except:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    raw_qr = body.get("qr_data")

    if not raw_qr:
        return JsonResponse({"error": "No QR data"}, status=400)

    print("RAW QR:", raw_qr)

    # =========================
    # 🔥 ПАРСИНГ
    # =========================
    try:
        parsed = json.loads(raw_qr)

        if isinstance(parsed, str):
            parsed = json.loads(parsed)

        print("PARSED:", parsed)

        sku = parsed.get("sku")
        data = parsed.get("data", {})

    except Exception as e:
        print("❌ PARSE ERROR:", e)
        sku = raw_qr
        data = None

    # =========================
    # 🔍 ИЩЕМ ПРОДУКТ
    # =========================
    product = Product.objects(sku=sku).first()

    if product:
        return JsonResponse({
            "found": True,
            "product": {
                "sku": product.sku,
                "name": product.name,
            }
        })

    # =========================
    # 🔥 ПРОВЕРКА ДАННЫХ
    # =========================
    required_fields = ["name", "manufacturer", "form", "dosage", "package_size"]

    missing_fields = []

    if data:
        for field in required_fields:
            if not data.get(field):
                missing_fields.append(field)

    # =========================
    # ❗ ЕСЛИ НЕ ХВАТАЕТ ДАННЫХ → ФОРМА
    # =========================
    if data and missing_fields:
        return JsonResponse({
            "found": False,
            "needs_input": True,
            "missing_fields": missing_fields,
            "sku": sku,
            "data": data
        })

    # =========================
    # 🔥 ЕСЛИ ВСЕ ДАННЫЕ ЕСТЬ → СОЗДАЕМ
    # =========================
    if data:
        product = Product(
            sku=sku,
            name=data.get("name"),
            manufacturer=data.get("manufacturer"),
            form=data.get("form"),
            dosage=data.get("dosage"),
            package_size=data.get("package_size"),
        )
        product.save()

        try:
            allocate_product_quantity(product, 10)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse({
            "found": False,
            "created": True,
            "product": {
                "sku": product.sku,
                "name": product.name,
            }
        })

    # =========================
    # ❌ ТОЛЬКО SKU → ФОРМА
    # =========================
    return JsonResponse({
        "found": False,
        "needs_input": True,
        "sku": sku,
        "data": {}
    })