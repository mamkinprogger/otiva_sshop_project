from django.shortcuts import render


async def index(request):
    # context = {}
    return render(request, 'main/index.html')

