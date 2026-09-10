import logging
import concurrent.futures
import sys
import threading
from typing import Any
from multiprocessing import get_context
from email.mime.multipart import MIMEMultipart

from chat.db_orm import orm_update_client_emails_history
from chat.utils import ShopEmail

logger = logging.getLogger("celery_logger")


class NotificationFromClient:
    def __init__(self, *,
                 manager_email: str = None,
                 emails_data: list[
                     tuple[int, str, list[str]] |
                     list[int | str| list[str]]
                 ] = None,
                 alias_keys: list[Any] = None,
                 ):
        self.manager_email = manager_email
        self.emails_data = None

        if emails_data:
            self._create_emails_data(emails_data, alias_keys)

    def _create_emails_data(self, emails_data: list[tuple[int, str, list[str]]], keys: list[Any]) -> None:
        if not isinstance(emails_data, list):
            raise TypeError("emails_data must be a list[tuple[client_id, topic, prev_emails]]")
        elif keys and not isinstance(keys, list):
            raise TypeError("keys must be a list[Any]")

        self.emails_data = {
            ind: {
                "client_id": mail[0],
                "topic": mail[1],
                "prev_emails": mail[2],
                "alias_key": keys[ind] if keys else None
            }
            for ind, mail in enumerate(emails_data)
        }

    def create_emails_list(self) -> list[MIMEMultipart]:
        """
        Create mails list for manager

        if emails_data is empty, return empty list

        :return: list[MIMEMultipart]
        """
        if not isinstance(self.manager_email, str):
            raise TypeError("manager_email must be a string")
        elif not self.emails_data:
            raise RuntimeError("emails_data must be passed")


        if not self.emails_data:
            return []

        mails_list = []
        if len(self.emails_data) == 1:
            key = list(self.emails_data)[0]
            msg = self.emails_data[key]
            mail = ShopEmail(self.manager_email, msg["topic"], msg["topic"]).create_mail(msg["prev_emails"])

            self.emails_data[mail["Message-ID"]] = self.emails_data.pop(key)
            mails_list.append(mail)
        else:
            cxt = get_context('spawn') if sys.platform == 'win32' else get_context('fork')
            with concurrent.futures.ProcessPoolExecutor(max_workers=8, mp_context=cxt) as executor:
                futures = [
                    [ind, executor.submit(ShopEmail(self.manager_email, mail["topic"], mail["topic"]).create_mail, mail["prev_emails"])]
                    for ind, mail in self.emails_data.items()
                ]
            for ind, future in futures:
                if future.exception() is not None:
                    self.emails_data.pop(ind)
                    logger.error(repr(future.exception()))
                else:
                    mail = future.result()
                    self.emails_data[mail["Message-ID"]] = self.emails_data.pop(ind)
                    mails_list.append(mail)
        return mails_list

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

    def update_clients_emails_history(self, results: list[tuple[str, bool]]) -> None:
        if len(results) == 1:
            mail_id, success = results[0]
            if not success:
                return
            mail = self.emails_data[mail_id]
            mail["prev_emails"].append(mail_id)
            orm_update_client_emails_history(mail["client_id"], mail["prev_emails"])
            return

        threads = []
        for mail_id, success in results:
            if not success:
                continue
            mail = self.emails_data[mail_id]
            mail["prev_emails"].append(mail_id)
            thread = threading.Thread(
                target=orm_update_client_emails_history,
                args=(mail["client_id"], mail["prev_emails"])
            )
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

    def get_notifications_results(self) -> list[list]:
        results = []
        for key in self.emails_data:
            msg = self.emails_data[key]
            success = msg.get("success", None)

            res = [msg["alias_key"], success] if msg["alias_key"] is not None else [key, success]
            if isinstance(success, bool) and not success:
                res.append(msg["fail_reason"])
            results.append(res)
        return results



def send_notification_on_email(
        manager_email: str,
        emails_data: list[tuple[int, str, list[str]]],
        alias_keys: list[Any] = None,
        view_result=False,
) -> None | list[list]:
    """Send out notification on managers email"""
    ns = NotificationFromClient(
        manager_email=manager_email,
        emails_data=emails_data,
        alias_keys=alias_keys
    )
    mails_list = ns.create_emails_list()
    results = ShopEmail().send_email_from_yandex(mails_list)

    ns.add_results_sending(results)
    ns.update_clients_emails_history([(mail_id, success) for mail_id, success, _ in results])
    return ns.get_notifications_results() if view_result else None
