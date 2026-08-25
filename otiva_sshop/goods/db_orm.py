from goods.models import AvitoProducts


def orm_get_avito_product(apid: int) -> str:
    """Get the name of an existing product via avito_product_id"""
    try:
        product_name = AvitoProducts.objects.filter(avito_product_id=apid).values_list("product__name").get()[0]
    except AvitoProducts.DoesNotExist:
        return "неверный продукт-id" # заглушка, сделать get-запрос к авито
    return product_name