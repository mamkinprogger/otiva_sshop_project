from django.db import models

from app.db.mixin import TimeStampMixin

class Pages(TimeStampMixin):
    """Page main"""
    title = models.CharField(max_length=250, verbose_name="Название вкладки")
    slug = models.SlugField(max_length=100, unique=True, blank=True, verbose_name="URL страницы")

    class Meta:
        db_table = 'page'
        verbose_name = "Страница"
        verbose_name_plural = "Страницы"
        ordering = ("title",)

    def __str__(self):
        return self.title


class MainBlocks(TimeStampMixin):
    """Main block of page"""
    title = models.CharField(max_length=250, blank=True, null=True, verbose_name="Подпись главного блока")
    text = models.TextField(blank=True, null=True, verbose_name="Текст главного блока")

    page = models.ForeignKey(Pages, on_delete=models.CASCADE)

    class Meta:
        db_table = 'main_block'
        verbose_name = "Главный блок страницы"
        verbose_name_plural = "Главные блоки страниц"
        ordering = ("id",)

    def __str__(self):
        return f"{self.page} — main_{self.title}"


class PageBlocks(TimeStampMixin):
    """Blocks of Pages"""
    title = models.CharField(max_length=250, blank=True, null=True, verbose_name="Подпись блока")
    text = models.TextField(blank=True, null=True, verbose_name="Текст блока")
    link_text = models.CharField(max_length=250, blank=True, verbose_name="Название гиперссылки")
    link_url = models.URLField(blank=True, verbose_name="Адрес на что ведет ссылка")
    display_order = models.PositiveSmallIntegerField(default=0, db_comment="Наивысший приоритет = 0 ", verbose_name="Приоритет выведения блоков")

    page = models.ForeignKey(Pages, on_delete=models.CASCADE)

    class Meta:
        db_table = 'block'
        verbose_name = "Блок страницы"
        verbose_name_plural = "Блоки страниц"
        ordering = ("id",)

    def __str__(self):
        return f"{self.page} — {self.title}"


class MotivationBlocks(TimeStampMixin):
    """Motivation block. Uniq tables for page main:index"""

    sticker = models.CharField(max_length=150, blank=True, null=True, verbose_name="Смайлик мотивационного блока")
    title = models.CharField(max_length=250, blank=True, null=True, verbose_name="Подпись мотивационного блока")
    text = models.TextField(blank=True, null=True, verbose_name="Текст мотивационного блока")

    page = models.ForeignKey(Pages, on_delete=models.CASCADE)

    class Meta:
        db_table = 'motivation_block'
        verbose_name = "Мотивационный блок страницы"
        verbose_name_plural = "Мотивационные блоки страниц"
        ordering = ("id",)

    def __str__(self):
        return f"{self.page} — {self.title}"
