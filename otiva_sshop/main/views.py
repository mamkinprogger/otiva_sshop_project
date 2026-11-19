import logging

from asgiref.sync import sync_to_async
from django.core.handlers.asgi import ASGIRequest
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse, Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from app.settings import K6_TEST_ENV, DEBUG, TESTING
from main.db_orm import orm_get_main_index_content, orm_get_about_content
from main.utils import LoadTestMixin

logger = logging.getLogger("root")

async def index(request: ASGIRequest):
    page_data = await orm_get_main_index_content("")
    return render(request, 'main/index.html', context=page_data)


async def about(request: ASGIRequest):
    page_data = await orm_get_about_content(request.get_full_path())
    page_data["main_block"].text = page_data["main_block"].text.split("\n")

    for block in page_data["blocks"]:
        text, _, bullets = block.text.partition("---")
        block.text = text.strip()
        setattr(block, "bullets", [i.rstrip for i in bullets.split("\n") if i.strip()])

    for qa in page_data["questions"]:
        qa.question = qa.question.rstrip("?")
    return render(request, 'main/about.html', context=page_data)


async def contacts(request: ASGIRequest):
    return render(request, 'main/contacts.html')


@method_decorator(csrf_exempt, name="dispatch")
class LoadTestView(LoadTestMixin, View):
    async def post(self, request: ASGIRequest):
        if True not in (K6_TEST_ENV, DEBUG, TESTING):
            raise Http404()

        if not self.check_auth(request.headers.get("Authorization")):
            return JsonResponse({"error": "Unauthorized"}, status=401)

        try:
            sql, params = self.check_valid_body(request)
        except RuntimeError as e:
            return JsonResponse({"error": e.args[0]}, status=400)

        try:
            result = await sync_to_async(self.execute_sql)(sql, params)
            return JsonResponse(result, encoder=DjangoJSONEncoder, json_dumps_params={"ensure_ascii": False})
        except Exception as e:
            logger.warning(f"SQL test endpoint execution failed {repr(e)}")
            return JsonResponse({"error": f"SQL execution failed: {repr(e)}"}, status=400)
