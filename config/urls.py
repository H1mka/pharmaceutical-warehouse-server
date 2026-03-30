"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from apps.products import views as products_views
from apps.storage_location import views as storage_location_views
from apps.inventory import views as inventory_views
from apps.logs import views as logs_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", products_views.home),

    # Product endpoints
    path(
        "products", 
        products_views.products_list_create, name="products_list_create"
    ),
    path(
        "products/<str:sku>", 
        products_views.product_detail, 
        name="product_detail"
    ),

    # Storage locations CRUD
    path(
        "storage-locations",
        storage_location_views.storage_location_list_create,
        name="storage_location_list_create",
    ),
    path(
        "storage-locations/<str:storage_location_id>",
        storage_location_views.storage_location_detail,
        name="storage_location_detail",
    ),

    # Inventory CRUD
    path(
        "inventory",
        inventory_views.inventory_list_create,
        name="inventory_list_create",
    ),
    path(
        "inventory/<str:inventory_id>",
        inventory_views.inventory_detail,
        name="inventory_detail",
    ),

    # Logs CRUD
    path(
        "logs",
        logs_views.logs_list_create,
        name="logs_list_create",
    ),
    path(
        "logs/",
        logs_views.logs_list_create,
        name="logs_list_create",
    ),
    path(
        "logs/<str:log_id>",
        logs_views.log_detail,
        name="log_detail",
    ),
]
