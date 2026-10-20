import concurrent.futures
import logging
import threading
from email.mime.multipart import MIMEMultipart
from typing import Any

from app.misc.redis_misc import sredis, redis_broker
from chat.db_orm import orm_get_or_create_client_from_his_msg, orm_update_client_emails_history, orm_update_manager_load
from chat.utils import ShopEmail, MessageFieldsException
from goods.db_orm import orm_get_avito_product
from users.models import ClientPermissionError

logger = logging.getLogger("celery_logger")

class EmailNotificationError(Exception):
    pass

class EmailNotificationTypeError(EmailNotificationError, TypeError):
    pass

class EmailNotificationFieldError(EmailNotificationError, KeyError):
    pass

class EmailNotificationNoData(EmailNotificationError, RuntimeError):
    pass


class EmailNotification:
    def __init__(
            self,
            manager_email: str = None,
            *,
            emails_data: list[
                tuple[int, str, str | None] |
                list[int | str| str | None]
            ] = None,
            alias_keys: list[Any] = None,
    ):
        self.manager_email = manager_email
        self.emails_data = None

        if emails_data:
            self._create_emails_data(emails_data, alias_keys)

    def _create_emails_data(self, emails_data: list[tuple[int, str, str]], keys: list[Any] | None) -> None:
        if not isinstance(emails_data, list):
            raise EmailNotificationTypeError("Emails_data must be a list[tuple[client_id, topic, prev_email]")
        elif keys and not isinstance(keys, list):
            raise EmailNotificationTypeError("keys must be a list[Any]")

        self.emails_data = {
            ind: {
                "client_id": mail[0],
                "topic": mail[1],
                "prev_email": mail[2],
                "alias_key": keys[ind] if keys and ind < len(keys) else None
            }
            for ind, mail in enumerate(emails_data)
        }

    def add_results_sending(self, results: list[tuple[str | int, bool, Any]]) -> None:
        """
        Extend notifications field results of sending

        :param results: list[(bool[success], uniq_id_message)]
        :return: None
        """
        for uniq_id, success, comment in results:
            self.emails_data[uniq_id]["success"] = success
            if not success:
                self.emails_data[uniq_id]["fail_reason"] = comment

    def get_notifications_results(self) -> list[list]:
        """
        :return: list[list[res_key, success, comment_if_fall]]
        """
        results = []
        for key in self.emails_data:
            msg = self.emails_data[key]
            success = msg.get("success", None)

            res = [msg["alias_key"], success] if msg["alias_key"] is not None else [key, success]
            if isinstance(success, bool) and not success:
                res.append(msg["fail_reason"])
            results.append(res)
        return results

    def _get_mail_entity_after_sending(self, email_id: str):
        try:
            mail = self.emails_data[email_id]
        except KeyError as err:
            raise EmailNotificationFieldError(f"Not Notification {email_id} in self.emails_data") from err
        return mail

    def update_client_emails(self, result: tuple[str, bool]) -> None:
        """
        :param result: (message_id, success)
        """
        email_id, success = result
        mail = self._get_mail_entity_after_sending(email_id)
        if not success:
            return
        else:
            mail["prev_email"] = email_id
            orm_update_client_emails_history(mail["client_id"], mail["prev_email"])

    def update_clients_emails(self, results: list[tuple[str, bool]]) -> None:
        """
        Pass results in sending order.

        Database update only the last message sent by the client.

        :param results: list[tuple[message_id, success]]
        """
        if len(results) == 1:
            self.update_client_emails(results[0])
            return

        threads = []
        updated_clients = set()

        for i in range(len(results)-1, -1, -1):
            result = results[i]
            email_id, success = result
            mail = self._get_mail_entity_after_sending(email_id)
            client_id = mail["client_id"]

            if not success:
                continue
            elif client_id in updated_clients:
                mail["prev_email"] = email_id
                continue

            thread = threading.Thread(target=self.update_client_emails, args=(result,))
            thread.start()
            threads.append(thread)
            updated_clients.add(client_id)

        for thread in threads:
            thread.join()

    def create_emails_list(self) -> list[MIMEMultipart]:
        """
        Create mails list for manager

        :return: list[MIMEMultipart]
        """
        if not isinstance(self.manager_email, str):
            raise EmailNotificationTypeError("Manager_email must be a string")
        elif not self.emails_data:
            raise EmailNotificationNoData("Emails_data must be passed")

        mails_list = []
        for key in list(self.emails_data):
            try:
                mail = self.emails_data[key]
                prev_emails = mail["prev_email"]
                email_id = redis_broker.rpop("mails_ids")
                if prev_emails:
                    prev_emails = [prev_emails]
                if email_id:
                    email_id = email_id.decode()

                email = ShopEmail(
                    self.manager_email,
                    mail["topic"],
                    mail["topic"]
                ).create_mail(prev_emails, email_id)

                self.emails_data[email["Message-ID"]] = self.emails_data.pop(key)
                mails_list.append(email)
            except Exception as e:
                self.emails_data.pop(key)
                logger.error(repr(e))
        return mails_list







def get_topic_and_prev_email(
        manager_id: int,
        client_id: int,
        chat_id: str,
        call: str | None,
        item_id: int | None,
        read: int | None = None,
        skipped_msg:int = 0
) -> tuple[dict[str, bool], str, str | None]: # вызвать ошибку если read
    """
    Update manager load and get previous mail from client
    If item_id passed, check existing item_id
    """
    client_db_data = orm_get_or_create_client_from_his_msg(
        manager_id,
        client_id,
        chat_id,
        skipped_msg
    )
    orm_update_manager_load(manager_id, call, client_db_data["client_added"])
    if read:
        raise EmailNotificationError("Message already read")

    product = "НеОбъявление"
    if item_id is not None:
        product = orm_get_avito_product(item_id)
    topic = f"{product}-{chat_id}:{client_db_data["client_name"]}"
    just_added = {
        "client": client_db_data["client_added"],
        "chat": client_db_data["chat_added"],
    }
    return just_added, topic, client_db_data["prev_email"]


def load_and_extend_data_for_email(manager_id: int, msgs: list[dict]) -> dict:
    """
    Makes db queries

    Check clients, create them if needed, if all good return messages for email
    :param manager_id: int
    :param msgs: dict[client_id, chat_id, call, new_chat, item_id]
    :return: dict[int, msg_data_with_emails_fields]
    """
    messages = {ind: msg for ind, msg in enumerate(msgs)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        try:
            futures = [
                [
                    sequence,
                    executor.submit(
                        get_topic_and_prev_email,
                        manager_id, message["client_id"], message["chat_id"],
                        message["call"], message["item_id"], message["read"], message["skipped_msgs"]
                    )
                ]
                for sequence, message in messages.items()
                ]
        except KeyError as err:
            raise MessageFieldsException(f"Message hasn't field {err}")

        for sequence, future in futures:
            exc = future.exception()
            if exc:
                if isinstance(exc, EmailNotificationError):
                    pass
                else:
                    logger.error(repr(future.exception()))
                    if isinstance(exc, ClientPermissionError) and messages[sequence]["new_chat"] is True:
                        sredis.hincrby("managers", str(manager_id), -1)
                messages.pop(sequence)
            else:
                _, topic, prev_email = future.result()
                messages[sequence]["topic"] = topic
                messages[sequence]["prev_email"] = prev_email
    return messages


def send_notifications_on_email(
        manager_email: str,
        emails_data: list[tuple[int, str, str]],
        alias_keys: list[Any] = None,
        view_result=False,
) -> None | list[list]:
    """
    Send out notification on managers email

    :param manager_email: str
    :param emails_data: list[tuple[client_id, subject, prev_email_id]]
    :param alias_keys: list[Any] - replace res_key on alias key. zip(emails_data, alias_keys)
    :param view_result: bool - return results of sending
    :return: list[list]
    """
    if not emails_data:
        return []

    ns = EmailNotification(
        manager_email=manager_email,
        emails_data=emails_data,
        alias_keys=alias_keys
    )
    mails_list = ns.create_emails_list()
    results = ShopEmail().send_email_from_yandex(mails_list)

    ns.add_results_sending(results)
    ns.update_clients_emails([(mail_id, success) for mail_id, success, _ in results])
    return ns.get_notifications_results() if view_result else None
