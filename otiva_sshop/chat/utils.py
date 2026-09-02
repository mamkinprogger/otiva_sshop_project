import logging
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

class CreateMailException(TypeError):
    pass

class InvalidMailFieldException(RuntimeError):
    pass


class MessageFromWebhook:
    def __init__(
            self,
            msg: dict = None,
            client_id: int = None,
            chat_id: str = None,
            sending_time: int = None,
            call: str = None,
            item_id: int = None,
            text: str = None,
            read: int = None,
            ):
        """update fields if msg passed"""
        self.client_id = client_id
        self.chat_id = chat_id
        self.sending_time = sending_time
        self.call = call
        self.item_id = item_id
        self.read = read
        self.text = text
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
            self.read = msg["read"]
            if msg["content"]:
                self.text = msg["content"].get("text", None)
                call = msg["content"].get("call", None)
                if call:
                    self.call = call["status"]
        except (KeyError, TypeError) as e:
            raise MessageFieldsException(f"В полях сообщения ошибка: {repr(e)}") from None

    def correct_chat_id(self) -> bool:
        if not isinstance(self.chat_id, str) or not self.chat_id:
            return False
        for i in self.chat_id:
            if i not in (string.ascii_letters + string.digits + "-_"):
                return False
        return True

    def correct_call(self) -> bool:
        if self.call is None:
            return True
        if self.call:
            return isinstance(self.call, str) and self.call.isalpha()
        return False

    @staticmethod
    def correct_positive_int_value(value: int) -> bool:
        return type(value) is int and value > 0

    def create(self) -> dict | str | bool :
        """create message_data for manager"""
        if None in (self.client_id, self.chat_id, self.sending_time):
            raise MessageFieldsException("The key required to create a message is missing")

        correct_msg = {
            "client_id": self.client_id,
            "chat_id": self.chat_id,
            "item_id": self.item_id,
            "sending_time": self.sending_time,
            "call": self.call,
            "text": self.text,
            "read": self.read,
        }
        if not all([
            self.correct_positive_int_value(self.client_id),
            self.correct_positive_int_value(self.sending_time),
            self.correct_positive_int_value(self.item_id) if self.item_id else True,
            self.correct_positive_int_value(self.read) if self.read else True,
            self.correct_chat_id(),
            self.correct_call(),
            isinstance(self.text, str) if self.text else True,
        ]):
            logger.error(f"Сообщение некорректно {correct_msg}")
            return False
        return correct_msg

    def create_str(self):
        return '~'.join(f"{k}:{v}" for k, v in self.create().items())

    def __str__(self):
        return f"{self.chat_id}:{self.sending_time}"


class SMTPEmailSender:
    def __init__(
            self,
            from_email: str,
            password: str,
            smtp_server: str = "smtp.yandex.com",
            port: int = 465,
            timeout: int = 7,
    ):
        self.from_email = from_email
        self.password = password
        self.smtp_server = smtp_server
        self.port = port
        self.timeout = timeout

        self.client: smtplib.SMTP_SSL | None = None
        self.ctx = ssl.create_default_context()

    def connect(self) -> None:
        """Open SSL connection to server"""
        self.client = smtplib.SMTP_SSL(
            self.smtp_server,
            self.port,
            context=self.ctx,
            timeout=self.timeout,
        )

        self.client.login(
            self.from_email,
            self.password,
        )

    def send(self, mail: MIMEMultipart) -> None:
        """
        Send mail on server

        Don't recommended use without context manager
        """
        if self.client is None:
            self.connect()

        try:
            self.client.sendmail(
                self.from_email,
                mail["To"],
                mail.as_string(),
            )
        except smtplib.SMTPServerDisconnected:
            logger.warning(
                "SMTP connection lost, reconnecting..."
            )

            self.close()
            self.connect()

            self.client.sendmail(
                self.from_email,
                mail["To"],
                mail.as_string(),
            )

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.quit()
            finally:
                self.client = None

    def __enter__(self) -> "SMTPEmailSender":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False


class ShopEmail:
    def __init__(
            self,
             to_email: str = None,
             subject: str = None,
             text: str = None
             ):
        self.from_email = ROOT_EMAIL
        self.password = EMAIL_PASSWORD
        self.to_email = to_email
        self.subject = subject if subject else ""
        self.text = text


    @staticmethod
    def valid_mails_ids(mails: list[str]) -> None:
        """Validation of emails ids"""
        valid_chars = set(string.ascii_letters + string.digits + ".@<>")

        if not isinstance(mails, list):
            raise CreateMailException("mails is not a list")
        elif len(mails) == 0:
            raise CreateMailException("not mails in list")

        for mail_id in mails:
            if not isinstance(mail_id, str):
                raise CreateMailException("mail_id is not a str")

            mail_id = mail_id.strip()
            if not mail_id:
                raise InvalidMailFieldException("mail_id is empty")

            if not all(char in valid_chars for char in mail_id):
                raise InvalidMailFieldException("mail_id contain invalid characters")

    @staticmethod
    def valid_email(email: str) -> bool:
        valid_chars = set(string.ascii_letters + string.digits + ".")
        if not isinstance(email, str):
            raise CreateMailException("email is not a str")

        email_data = email.split("@")
        if len(email_data) != 2 or len(email_data[1].rsplit(".", 1)) != 2:
            return False

        email_name, email_domain = email_data
        if not email_name or email_name[0] in string.digits:
            return False
        if not all(char in valid_chars for char in email_name):
            return False

        return True

    def create_mail(self, prev_mails: list[str] = None,) -> MIMEMultipart:
        """Create email with MIME"""
        if not isinstance(self.subject, str):
            raise CreateMailException("subject is not a str")

        if not all([
            self.valid_email(self.to_email),
            not self.text or isinstance(self.text, str)
        ]):
            raise InvalidMailFieldException("Head of email is invalid")

        msg = MIMEMultipart()
        msg['Message-ID'] = make_msgid(EMAIL_DOMAIN_NAME)
        msg['From'] = self.from_email
        msg['To'] = self.to_email
        sbj = self.subject


        if prev_mails:
            try:
                self.valid_mails_ids(prev_mails)
                msg["Subject"] = f"Re: {sbj}"
                msg['In-Reply-To'] = prev_mails[-1]
                msg['References'] = " ".join(prev_mails)
            except (CreateMailException, InvalidMailFieldException):
                logger.warning(f"Не удалось прикрепить предыдущие сообщения для {msg["Message-ID"]}")
                msg["Subject"] = sbj
        else:
            msg["Subject"] = sbj

        if self.text:
            msg.attach(MIMEText(self.text, 'plain'))
        return msg

    def send_email_from_yandex(
            self,
            emails: list[MIMEMultipart],
    ) -> list[tuple[str, bool]]:
        """
        Send an email with an SMTP server. Establishes connection immediately over ssl
        :return: list[tuple[str[mail_id], bool[success]]]
        """
        smtp_server = "smtp.yandex.com"
        port = 465
        timeout = 7

        results = []
        for email in emails:
            try:
                with SMTPEmailSender(self.from_email, self.password, smtp_server, port, timeout) as sender:
                        sender.send(email)
                        results.append((email["Message-ID"], True))
            except smtplib.SMTPException as smtp_err:
                logger.error(f'Ошибка с SMTP {smtp_err}')
                results.append((email["Message-ID"], False))
                raise smtp_err
            except Exception as err:
                logger.error(f"Непредвиденная ошибка {err}", exc_info=True)
                results.append((email["Message-ID"], False))
                raise err
        return results