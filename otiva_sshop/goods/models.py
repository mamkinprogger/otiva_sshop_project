from django.db import models

from app.db.mixin import TimeStampMixin




class Categories(TimeStampMixin):
    """otiva_app fields"""
    name = models.CharField(max_length=200, unique=True, null=False, verbose_name='Название')
    slug = models.SlugField(max_length=200, unique=True, null=False, verbose_name="Сайт-URL")
    special = models.BooleanField(default=False, verbose_name='Уникальная категория')


    class Meta:
        db_table = 'category'
        verbose_name = 'Категорию'
        verbose_name_plural = 'Категории'
        ordering = ("id",)

    def __str__(self):
        return f"{self.name} - {self.id}"


class AvitoCategories(TimeStampMixin):
    """API fields"""
    avito_category_id = models.PositiveBigIntegerField(unique=True, verbose_name="Авито-Категория-ID")
    name = models.CharField(max_length=200, unique=True, verbose_name="Авито-Категория-Название")

    category = models.ForeignKey(
        to=Categories,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name="Категория"
    )

    class Meta:
        db_table = 'avito_category'
        verbose_name = 'Авито-Категорию'
        verbose_name_plural = 'Авито-Категории'
        ordering = ("id",)

    def __str__(self):
        return f"{self.name} {self.avito_category_id}"


class Products(TimeStampMixin):
    """otiva_app fields"""
    name = models.CharField(max_length=200, unique=True, null=False, verbose_name='Название')
    slug = models.SlugField(max_length=200, unique=True, null=True, verbose_name="site_URL")
    special = models.BooleanField(default=False, verbose_name='Уникальный товар')

    image = models.ImageField(upload_to="goods_images", blank=True, null=True, verbose_name="Фотка")
    discount = models.DecimalField(default=0.00, max_digits=4, decimal_places=2, verbose_name="Скидка в %")
    price = models.IntegerField(default=0, verbose_name='Цена')
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")

    category = models.ForeignKey(to=Categories, on_delete=models.CASCADE, verbose_name="Категория")

    class Meta:
        db_table = 'product'
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ("id",)

    def __str__(self):
        return f"{self.name} Количество - {self.quantity}"

    def sell_price(self):
        """Sell price if order from site"""
        if self.discount:
            return round(self.price - self.price * self.discount / 100)
        return self.price


class AvitoProducts(TimeStampMixin):
    """API fields"""
    avito_product_id = models.PositiveBigIntegerField(unique=True, verbose_name="Авито-Товар-ID")
    url = models.URLField(max_length=200, unique=True, null=True, blank=True, verbose_name="Авито-Ссылка на объявление")
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="Дата создания объявления")
    finish_time = models.DateTimeField(null=True, blank=True, verbose_name="Дата завершения объявления")
    status = models.CharField(max_length=20, verbose_name="Статус размещения объявления")

    """otiva_app fields"""
    updated_product = models.DateTimeField(null=True, blank=True, verbose_name="Дата обновления объявления")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество")

    avito_category = models.ForeignKey(
        to=AvitoCategories,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    product = models.ForeignKey(
        to=Products,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    class Meta:
        db_table = 'avito_product'
        verbose_name = 'Авито-Товар'
        verbose_name_plural = 'Авито-Товары'
        ordering = ("id",)

    def __str__(self):
        return f"{self.avito_product_id} Количество - {self.quantity}"




