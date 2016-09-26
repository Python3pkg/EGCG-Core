from egcg_core.app_logging import AppLogger
from egcg_core.config import cfg
from .asana_notification import AsanaNotification
from .email_notification import EmailNotification
from .log_notification import LogNotification


class NotificationCentre(AppLogger):
    def __init__(self, name):
        self.name = name
        self.subscribers = []

    def setup_subscribers(self, *subscribers):
        for s in subscribers:
            if cfg.query('notifications', s.config_domain):
                self.subscribers.append(s)
            else:
                self.warning('No config found for ' + s.__class__.__name__)

    def notify(self, msg):
        for s in self.subscribers:
            s.notify(msg)
