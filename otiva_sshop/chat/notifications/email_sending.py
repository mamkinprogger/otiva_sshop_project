from chat.db_orm import orm_update_client_emails_history
from chat.utils import ShopEmail


def send_on_email(
        client_id: int,
        manager_email: str,
        subject: str,
        previous_emails: list[str]
) -> None:
    """Send out notification on managers email"""
    mail = ShopEmail(manager_email, subject, subject).create_mail(previous_emails)
    results = ShopEmail().send_email_from_yandex([mail])

    for mail_id, success in results:
        if success:
            previous_emails.append(mail_id)
            orm_update_client_emails_history(client_id, previous_emails)