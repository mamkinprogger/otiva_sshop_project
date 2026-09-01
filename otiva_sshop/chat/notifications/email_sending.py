import sys
import logging
import threading
import concurrent.futures
from multiprocessing import get_context
from email.mime.multipart import MIMEMultipart

from chat.db_orm import orm_update_client_emails_history
from chat.utils import ShopEmail

logger = logging.getLogger("celery_logger")


def update_clients_emails_history(
        results_of_sending: list[tuple[str, bool]],
        mails_list: list[list[int | MIMEMultipart]]
) -> None:
    """
    Гpdates the message history based on the results of the mailing
    :param results_of_sending:
    :param mails_list:
    """
    if len(results_of_sending) == 1:
        mail_id, success = results_of_sending[0]
        if not success:
            return
        for client_id, mail in mails_list:
            if mail['Message-ID'] == mail_id:
                previous_emails = mail["References"].split() if "References" in mail else []
                previous_emails.append(mail_id)
                orm_update_client_emails_history(client_id, previous_emails)
                return

    threads = []
    for mail_id, success in results_of_sending:
        if not success:
            continue
        for client_id, mail in mails_list:
            if mail['Message-ID'] == mail_id:
                previous_emails = mail["References"].split() if "References" in mail else []
                previous_emails.append(mail_id)
                thread = threading.Thread(
                    target=orm_update_client_emails_history,
                    args=(client_id, previous_emails)
                )
                thread.start()
                threads.append(thread)
    for thread in threads:
        thread.join()


def create_mails_list(
        manager_email: str,
        emails_data: list[tuple[int, str, list]],
) -> list[list[int | MIMEMultipart]]:
    """
    Create mails list for manager

    if emails_data is empty, return empty list

    :return: list[list[client_id, MIMEMultipart]]
    """
    if not emails_data:
        return []

    mails_list= []
    if len(emails_data) == 1:
        client_id, subject, prev_mails = emails_data[0]
        mail = ShopEmail(manager_email, subject, subject).create_mail(prev_mails)
        mails_list.append([client_id, mail])
    else:
        cxt = get_context('spawn') if sys.platform == 'win32' else get_context('fork')
        with concurrent.futures.ProcessPoolExecutor(max_workers=8, mp_context=cxt) as executor:
            futures = [
                executor.submit(
                    ShopEmail(manager_email, subject, subject).create_mail, prev_mails
                )
                for client_id, subject, prev_mails in emails_data
            ]
        for ind, future in enumerate(futures):
            if future.exception() is not None:
                logger.error(repr(future.exception()))
            else:
                client_id = emails_data[ind][0]
                mails_list.append([client_id, future.result()])
    return mails_list


def send_on_email(
        manager_email: str,
        emails_data: list[tuple[int, str, list]],
) -> None:
    """Send out notification on managers email"""
    mails_list = create_mails_list(manager_email, emails_data)
    results = ShopEmail().send_email_from_yandex([mail for _, mail in mails_list])
    update_clients_emails_history(results, mails_list)
