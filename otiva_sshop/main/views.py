from django.http import HttpResponse

from otiva_shop.settings import TIME_ZONE


async def index(request):
    print(TIME_ZONE)
    return HttpResponse("Хаюшки")

