from django.shortcuts import render

from main.db_orm import orm_get_main_index_content


async def index(request):
    page_data = await orm_get_main_index_content("")
    return render(request, 'main/index.html', context=page_data)

