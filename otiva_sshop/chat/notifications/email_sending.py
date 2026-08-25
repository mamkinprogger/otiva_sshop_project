from chat.db_orm import orm_update_client_emails_history
from chat.utils import SendEmail


def send_on_email(
        client_id: int,
        manager_email: str,
        subject: str,
        previous_emails: list
) -> None:
    """Send out notification on managers email"""
    email_id = SendEmail(manager_email, subject, subject).send_email_from_yandex(previous_emails)
    previous_emails.append(email_id)
    orm_update_client_emails_history(client_id, previous_emails)