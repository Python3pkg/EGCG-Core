from os.path import join, dirname, abspath
import jinja2
import smtplib
from time import sleep
from email.mime.text import MIMEText
from egcg_core.exceptions import EGCGError
from .notification import Notification


class EmailNotification(Notification):
    def __init__(self, name, mailhost, port, sender, recipients, strict=False, email_template=None):
        super().__init__(name)
        self.mailhost = mailhost
        self.port = port
        self.sender = sender
        self.recipients = recipients
        self.strict = strict
        self.email_template = email_template
        if email_template is None:
            self.email_template = join(dirname(abspath(__file__)), '..', '..', 'etc', 'email_notification.html')

    def _notify(self, body):
        msg = self._prepare_message(body)
        mail_success = self._try_send(msg)
        if not mail_success:
            if self.strict is True:
                raise EGCGError('Failed to send message: ' + body)
            else:
                self.critical('Failed to send message: ' + body)

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
            else:
                return False

    def _prepare_message(self, body):
        """
        Use Jinja to build a MIMEText html-formatted email.
        :param str body: The main body of the email to send
        """
        content = jinja2.Template(open(self.email_template).read())
        msg = MIMEText(
            content.render(title=self.name, body=self._prepare_string(body, {' ': '&nbsp', '\n': '<br/>'})),
            'html'
        )

        msg['Subject'] = self.name
        msg['From'] = self.sender
        msg['To'] = ','.join(self.recipients)
        return msg

    @staticmethod
    def _prepare_string(in_string, charmap):
        for k in charmap:
            in_string = in_string.replace(k, charmap[k])
        return in_string

    def _connect_and_send(self, msg):
        connection = smtplib.SMTP(self.mailhost, self.port)
        connection.send_message(
            msg,
            self.sender,
            self.recipients
        )
        connection.quit()
