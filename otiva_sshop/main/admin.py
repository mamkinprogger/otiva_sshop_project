from django.contrib import admin

from app.settings import DEBUG
from main.models import Pages, MainBlocks, PageBlocks, MotivationBlocks, RegularQuestions


class RootPageMixin:
    @staticmethod
    def root_page(title: str, *, page_main_block: bool = None, page_block: bool = None) -> str:
        page_title = "Страница не найдена"
        if page_main_block:
            page_title = MainBlocks.objects.filter(title=title).values_list("page__title").first()
        elif page_block:
            page_title = PageBlocks.objects.filter(title=title).values_list("page__title").first()
        return page_title


class MotivationBlocksTabAdmin(admin.TabularInline):
    model = MotivationBlocks
    fields = ["sticker", "title", "text"]
    extra = 1

class RegularQuestionsTabAdmin(admin.TabularInline):
    model = RegularQuestions
    fields = ["question", "answer", "display_order"]
    extra = 1


@admin.register(Pages)
class PagesAdmin(admin.ModelAdmin):
    list_display = ["title", "slug"]

    search_fields = ["title", "slug"]
    list_filter = ["title"]
    ordering = ["title"]

    def get_readonly_fields(self, request, obj=None):
        return [] if DEBUG else ["slug"]

    def get_inline_instances(self, request, obj: Pages | None = None):
        inline_instances = []
        if obj:
            if obj.slug.strip() == "":
                inline_instances.append(MotivationBlocksTabAdmin(self.model, self.admin_site))
            if obj.slug.strip("/") == "about":
                inline_instances.append(RegularQuestionsTabAdmin(self.model, self.admin_site))
        return inline_instances


@admin.register(MainBlocks)
class MainBlocksAdmin(RootPageMixin, admin.ModelAdmin):
    list_display = ["title", "root_page_title"]
    search_fields = ["title", "text", "page__title"]
    list_filter = ["title", "page__title"]
    ordering = ["page__title"]

    @admin.display(description="Название вкладки")
    def root_page_title(self, obj: MainBlocks) -> str:
        return super().root_page(obj.title, page_main_block=True)


@admin.register(PageBlocks)
class PageBlocksAdmin(RootPageMixin, admin.ModelAdmin):
    list_display = ["title", "display_order", "root_page_title"]
    search_fields = ["page__title", "display_order", "title", "text", "link_text", "link_url"]
    list_filter = ["page__title", "display_order", "title", "link_text", "link_url",]
    ordering = ["page__title", "display_order"]

    @admin.display(description="Название вкладки")
    def root_page_title(self, obj: PageBlocks) -> str:
        return super().root_page(obj.title, page_block=True)
