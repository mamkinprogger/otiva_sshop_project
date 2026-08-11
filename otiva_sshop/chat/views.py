import json
import logging

from django.http import HttpResponse, Http404, HttpRequest
from django.views.decorators.csrf import csrf_exempt

from chat.notifications.email_sending import send_message_from_storage
from chat.utils import create_correct_msg


logger = logging.getLogger("chat_logger")

@csrf_exempt
async def webhook(request: HttpRequest):
    """
    Receives a message from the API
    """
    if request.method != "POST":
        raise Http404()

    try:
        message = json.loads(request.body)
        if message["payload"]["type"] != "message":
            return HttpResponse()
        msg_to_queue = create_correct_msg(message["payload"]["value"])

        await send_message_from_storage(msg_to_queue)
    except (KeyError, TypeError) as e:
        logger.warning(f"Не удалось положить сообщение от webhook в очередь {repr(e)}")
        logger.error(f"\nОбъект сообщения\n"
                       f"{request.body}")
    except Exception as e:
        logger.warning(
            f"Не удалось положить сообщение от webhook в очередь Непредвиденная ошибка: {e}",
            exc_info=True
        )
    return HttpResponse()
