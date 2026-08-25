import logging
import os
import string

import smtplib
import ssl

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid

from app.settings import ROOT_EMAIL, EMAIL_PASSWORD, EMAIL_DOMAIN_NAME

logger = logging.getLogger("chat_logger")

class MessageFieldsException(KeyError):
    pass


class MessageFromWebhook:
    def __init__(self, msg: dict | None = None) -> None:
        """update fields if msg passed"""
        self.client_id = None
        self.chat_id = None
        self.sending_time = None
        self.call = None
        self.item_id = None
        self.message = None
        if msg:
            if not isinstance(msg, dict):
                raise MessageFieldsException("msg must be a dict")
            self.get_fields_from_msg(msg)

    def get_fields_from_msg(self, msg: dict):
        """
        Get fields from dict_message
        fields: autor_id, chat_id, created, content[call][status]
        """
        try:
            self.client_id = msg["author_id"]
            self.chat_id = msg["chat_id"]
            self.sending_time = msg["created"]
            self.item_id = msg["item_id"]
            if msg["content"]:
                self.message = msg["content"].get("text", None)
                call = msg["content"].get("call", None)
                if call:
                    self.call = call["status"]
        except (KeyError, TypeError) as e:
            raise MessageFieldsException(f"В полях сообщения ошибка: {repr(e)}")

    def correct_chat_id(self, chat_id: str | None = None) -> bool:
        field = self.chat_id if chat_id is None else chat_id
        if not isinstance(field, str) or not field:
            return False
        for i in field:
            if i not in (string.ascii_letters + string.digits + "-_"):
                return False
        return True

    def correct_call(self, call: str | None = None) -> bool:
        field = self.call if call is None else call
        if field is None:
            return True
        if field:
            return isinstance(field, str) and field.isalpha()
        return False

    def correct_positive_int_value(self, value: int) -> bool:
        return type(value) is int and value > 0

    def create(self) -> dict | bool:
        """create message_data for manager"""
        if None in (self.client_id, self.chat_id, self.sending_time):
            raise RuntimeError("Message_data didn't passed")

        correct_msg = {
            "client_id": self.client_id,
            "chat_id": self.chat_id,
            "item_id": self.item_id,
            "sending_time": self.sending_time,
            "call": self.call,
        }
        if not all([
            self.correct_positive_int_value(self.client_id),
            self.correct_positive_int_value(self.sending_time),
            self.correct_positive_int_value(self.item_id) if self.item_id else True,
            self.correct_chat_id(),
            self.correct_call(),
        ]):
            logger.error(f"Сообщение некорректно {correct_msg}")
            return False
        return correct_msg

    def __str__(self):
        return f"{self.sending_time}"


class SendEmail:
    def __init__(
            self,
             to_email: str = None,
             subject: str = None,
             text: str = None
             ):
        self.from_email = ROOT_EMAIL
        self.password = EMAIL_PASSWORD
        self.to_email = to_email
        self.subject = subject
        self.text = text

    def create_mail(self, prev_mails: list[str], **kwargs) -> MIMEMultipart:
        msg = MIMEMultipart()
        msg['Message-ID'] = make_msgid(EMAIL_DOMAIN_NAME)
        msg['From'] = self.from_email if not kwargs else kwargs["from_email"]
        msg['To'] = self.to_email if not kwargs else kwargs["to_email"]
        sbj = self.subject if not kwargs else kwargs["subject"]
        if prev_mails:
            msg["Subject"] = f"Re: {sbj}"
            msg['In-Reply-To'] = prev_mails[-1]
            msg['References'] = " ".join(prev_mails)
        else:
            msg["Subject"] = sbj

        if self.text or kwargs:
            msg.attach(MIMEText(self.text, 'plain')) if self.text else kwargs["text"]
        return msg


    def send_email_from_yandex(
            self,
            prev_mails_ids: list[str],
            smtp_server="smtp.yandex.com",
            port=465,
            timeout=5
    ) -> str:
        """
        Send an email with an SMTP server. Establishes connection immediately over ssl
        return mail_id if email was sent successfully
        """
        mail = self.create_mail(prev_mails_ids)
        ctx = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL(smtp_server, port, context=ctx, timeout=timeout) as client:
                client.login(self.from_email, self.password)
                client.sendmail(self.from_email, self.to_email, mail.as_string())
            return mail["Message-ID"]
        except smtplib.SMTPException as smtp_err:
            logger.error(f'Ошибка с SMTP {smtp_err}')
            raise RuntimeError("Mail не отправился из-за ошибки с SMTP") from smtp_err
        except Exception as err:
            logger.error(f"Непредвиденная ошибка {err}", exc_info=True)
            raise err
