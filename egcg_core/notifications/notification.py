from egcg_core.app_logging import AppLogger


class Notification(AppLogger):
    preprocess = None

    def __init__(self, name):
        self.name = name

    def _notify(self, msg):
        raise NotImplementedError

    def notify(self, msg):
        if self.preprocess:
            msg = self.preprocess(msg)
        return self._notify(msg)

    @staticmethod
    def preprocess_message(msg):
        return msg
