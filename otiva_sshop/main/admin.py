from django.contrib import admin

from app.settings import DEBUG
from main.models import Pages, MainBlocks, PageBlocks, MotivationBlocks


class MotivationBlocksTabAdmin(admin.TabularInline):
    model = MotivationBlocks
    fields = ["sticker", "title", "text"]
    extra = 1

@admin.register(Pages)
class PagesAdmin(admin.ModelAdmin):
    list_display = ["title", "slug"]

    search_fields = ["title", "slug"]
    list_filter = ["title"]
    readonly_fields = ["slug"]
    if DEBUG:
        readonly_fields = []
    ordering = ["title"]

    inlines = [MotivationBlocksTabAdmin]

@admin.register(MainBlocks)
class MainBlocksAdmin(admin.ModelAdmin):
    list_display = ["title", "text"]
    search_fields = ["title", "text", "page__title"]
    list_filter = ["title", "page__title"]
    ordering = ["page__title"]


@admin.register(PageBlocks)
class PageBlocksAdmin(admin.ModelAdmin):
    list_display = ["title", "text"]
    search_fields = ["page__title", "title", "text", "link_text", "link_url", ]
    list_filter = ["page__title", "title", "link_text", "link_url",]
    ordering = ["page__title"]
