from django.shortcuts import render


async def index(request):
    context = {
        "title": "Otiva - Главная",
        "content_head": "Добро пожаловать",
        "content": "Это главная страница."
    }
    return render(request, 'main/index.html', context=context)

