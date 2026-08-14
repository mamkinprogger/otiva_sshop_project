from django.contrib import admin
from django.contrib.auth.models import Group

from goods.models import Categories, AvitoCategories, AvitoProducts, Products

admin.site.unregister(Group)


class AvitoCatTabAdmin(admin.TabularInline):
    model = AvitoCategories
    fields = ["name", "avito_category_id"]
    readonly_fields = ["name", "avito_category_id"]
    extra = 0


class AvitoProductTabAdmin(admin.TabularInline):
    model = AvitoProducts
    fields = ["avito_product_id", "status", "quantity", "url"]
    readonly_fields = ["avito_product_id", "status", "quantity", "url"]
    extra = 0


class ProductsTabAdmin(admin.TabularInline):
    model = Products
    fields = ["name", "special"]
    readonly_fields = ["name", "special"]
    extra = 0


@admin.register(Categories)
class CategoriesAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = [
        "name",
        "special",
        'created_at',
        'updated_at'
    ]
    search_fields = ["name"]
    list_filter = ["special"]

    inlines = [ProductsTabAdmin, AvitoCatTabAdmin]


@admin.register(AvitoCategories)
class AvitoCategoriesAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "avito_category_id",
        'created_at',
        'updated_at'
    ]
    search_fields = ["name", "avito_category_id"]
    list_filter = ["name"]

    inlines = [AvitoProductTabAdmin]



@admin.register(Products)
class ProductsAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = [
        "name",
        "quantity",
        "price",
        "discount",
        "special",
        'created_at',
        'updated_at'
    ]
    search_fields = ["name"]
    list_filter = ["quantity", "special"]

    inlines = [AvitoProductTabAdmin]


@admin.register(AvitoProducts)
class AvitoProductsAdmin(admin.ModelAdmin):
    list_display = [
        'avito_product_id',
        'product_name',
        'quantity',
        'created_at',
        'updated_at'
    ]
    search_fields = ["avito_product_id"]

    @admin.display(description="Товар")
    def product_name(self, obj):
        return obj.product.name




