import logging
from .notification import Notification


class LogNotification(Notification):
    """Logs via log_cfg, and also to a notification file with the format'[date time][dataset_name] msg'"""

    config_domain = 'log'

    def __init__(self, name):
        super().__init__(name)
        handler = logging.FileHandler(filename=self.config['log_file'], mode='a')
        handler.setFormatter(
            logging.Formatter(
                fmt='[%(asctime)s][' + self.name + '] %(message)s',
                datefmt='%Y-%b-%d %H:%M:%S'
            )
        )
        handler.setLevel(logging.INFO)
        self._logger.addHandler(handler)

    def notify(self, msg):
        self.info(msg)
