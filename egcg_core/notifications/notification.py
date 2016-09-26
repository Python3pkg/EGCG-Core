from egcg_core.config import cfg
from egcg_core.app_logging import AppLogger


class Notification(AppLogger):
    config_domain = 'generic'

    def __init__(self, name):
        self.name = name
        self.config = cfg['notifications'][self.config_domain]

    def notify(self, msg):
        raise NotImplementedError
