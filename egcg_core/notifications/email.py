import jinja2
import smtplib
from time import sleep
from email.mime.text import MIMEText
from egcg_core.exceptions import EGCGError
from egcg_core.app_logging import AppLogger
from .notification import Notification


class Emailer(AppLogger):
    translation_map = {' ': '&nbsp', '\n': '<br/>'}

    def __init__(self, mailhost, port, sender, recipients, default_subject, email_template=None, strict=False):
        self.mailhost = mailhost
        self.port = port
        self.sender = sender
        self.recipients = recipients
        self.default_subject = default_subject
        self.email_template = email_template
        self.strict = strict

    def send_msg(self, msg, subject=None):
        email = self.build_email(msg, subject)
        success = self._try_send(email)
        if not success:
            err_msg = 'Failed to send message: ' + str(msg)
            if self.strict:
                raise EGCGError(err_msg)
            else:
                self.critical(err_msg)

    def _try_send(self, msg, retries=3):
        """
        Prepare a MIMEText message from body and diagnostics, and try to send a set number of times.
        :param int retries: Which retry we're currently on
        :return: True if a message is sucessfully sent, otherwise False
        """
        try:
            self._connect_and_send(msg)
            return True
        except (smtplib.SMTPException, TimeoutError) as e:
            retries -= 1
            self.warning('Encountered a %s exception. %s retries remaining', str(e), retries)
            if retries:
                sleep(2)
                return self._try_send(msg, retries)

            return False

    def build_email(self, body, subject=None):
        """
        Use Jinja to build a MIMEText html-formatted email from plain text.
        :param str body: The main body of the email to send
        :param str subject: Custom email subject line (default is self.default_subject)
        """
        if self.email_template:
            content = jinja2.Template(open(self.email_template).read())
            msg = MIMEText(content.render(title=subject, body=self._prepare_string(body)), 'html')
        else:
            msg = MIMEText(body)

        msg['Subject'] = subject or self.default_subject
        msg['From'] = self.sender
        msg['To'] = ', '.join(self.recipients)
        return msg

    @classmethod
    def _prepare_string(cls, msg):
        for k in cls.translation_map:
            msg = msg.replace(k, cls.translation_map[k])
        return msg

    def _connect_and_send(self, msg):
        connection = smtplib.SMTP(self.mailhost, self.port)
        connection.send_message(msg, self.sender, self.recipients)
        connection.quit()


class EmailNotification(Notification):
    def __init__(self, name, mailhost, port, sender, recipients, email_template=None, strict=False):
        super().__init__(name)
        self.emailer = Emailer(mailhost, port, sender, recipients, name, email_template, strict)

    def notify(self, msg):
        self.emailer.send_msg(msg)
