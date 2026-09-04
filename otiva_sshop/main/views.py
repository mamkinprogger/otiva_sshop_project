from django.http import HttpResponse
from django.shortcuts import render

from main.db_orm import orm_get_main_index_content, orm_get_about_content


async def index(request):
    page_data = await orm_get_main_index_content("")
    return render(request, 'main/index.html', context=page_data)


async def about(request):
    page_data = await orm_get_about_content(request.get_full_path())
    page_data["main_block"].text = page_data["main_block"].text.split("\n")

    for block in page_data["blocks"]:
        text, _, bullets = block.text.partition("---")
        block.text = text.strip()
        setattr(block, "bullets", [i.rstrip for i in bullets.split("\n") if i.strip()])

    for qa in page_data["questions"]:
        qa.question = qa.question.rstrip("?")
    return render(request, 'main/about.html', context=page_data)
