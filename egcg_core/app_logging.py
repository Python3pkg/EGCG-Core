from sys import stdout
import logging
import logging.config
import logging.handlers
from egcg_core.config import cfg


class LoggingConfiguration:
    """Stores Loggers, Formatters and Handlers"""

    default_fmt = '[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
    default_datefmt = '%Y-%b-%d %H:%M:%S'
    _formatter = None
    _default_formatter = None

    def __init__(self, config):
        self.cfg = config
        self.blank_formatter = logging.Formatter()
        self.handlers = set()
        self.loggers = {}
        self.log_level = logging.INFO

    @property
    def formatter(self):
        if self._formatter is None:
            self._formatter = self.default_formatter
        return self._formatter

    @property
    def default_formatter(self):
        if self._default_formatter is None:
            self._default_formatter = logging.Formatter(
                fmt=self.cfg.get('format', self.default_fmt),
                datefmt=self.cfg.get('datefmt', self.default_datefmt)
            )
        return self._default_formatter

    def get_logger(self, name, level=None):
        """
        Return a logging.Logger object with formatters and handlers added.
        :param name: Name to assign to the logger (usually __name__)
        :param int level: Log level to assign to the logger upon creation
        """
        if name in self.loggers:
            logger = self.loggers[name]
        else:
            logger = logging.getLogger(name)
            self.loggers[name] = logger

        if level is None:
            level = self.log_level
        logger.setLevel(level)
        for h in self.handlers:
            logger.addHandler(h)

        return logger

    def add_handler(self, handler, level=logging.NOTSET):
        """
        Add a created handler, set its format/level if needed and register all loggers to it
        :param logging.Handler handler:
        :param int level: Log level to assign to the created handler
        """
        if level == logging.NOTSET:
            level = self.log_level
        handler.setLevel(level)
        handler.setFormatter(self.formatter)
        for name in self.loggers:
            self.loggers[name].addHandler(handler)
        self.handlers.add(handler)

    def add_stdout_handler(self, level=logging.INFO):
        self.add_handler(logging.StreamHandler(stdout), level=level)

    def set_log_level(self, level):
        self.log_level = level
        for h in self.handlers:
            h.setLevel(self.log_level)
        for name in self.loggers:
            self.loggers[name].setLevel(self.log_level)

    def set_formatter(self, formatter):
        """
        Set all handlers to use formatter
        :param logging.Formatter formatter:
        """
        self._formatter = formatter
        for h in self.handlers:
            h.setFormatter(self.formatter)

    def configure_handlers_from_config(self):
        configurator = logging.config.BaseConfigurator({})
        handler_classes = {
            'stream_handlers': logging.StreamHandler,
            'file_handlers': logging.FileHandler,
            'timed_rotating_file_handlers': logging.handlers.TimedRotatingFileHandler
        }

        for handler_type in handler_classes:
            for handler_cfg in self.cfg.get(handler_type, []):
                level = logging.getLevelName(handler_cfg.pop('level', self.log_level))

                if 'stream' in handler_cfg:
                    handler_cfg['stream'] = configurator.convert(handler_cfg['stream'])
                handler = handler_classes[handler_type](**handler_cfg)
                self.add_handler(handler, level)


logging_default = LoggingConfiguration(cfg)


class AppLogger:
    """
    Mixin class for logging. An object subclassing this can log using its class name. Contains a
    logging.Logger object and exposes its log methods.
    """
    log_cfg = logging_default
    __logger = None

    def debug(self, msg, *args):
        self._logger.debug(msg, *args)

    def info(self, msg, *args):
        self._logger.info(msg, *args)

    def warning(self, msg, *args):
        self._logger.warning(msg, *args)

    def error(self, msg, *args):
        self._logger.error(msg, *args)

    def critical(self, msg, *args):
        self._logger.critical(msg, *args)

    @property
    def _logger(self):
        if self.__logger is None:
            self.__logger = self.log_cfg.get_logger(self.__class__.__name__)
        return self.__logger
