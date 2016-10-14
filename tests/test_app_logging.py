import os
import sys
import logging
import logging.handlers
from tests import TestEGCG
from egcg_core import app_logging
from egcg_core.config import cfg
cfg.load_config_file(TestEGCG.etc_config)


class TestLoggingConfiguration(TestEGCG):
    def setUp(self):
        self.log_cfg = app_logging.LoggingConfiguration(cfg['logging'])

    def tearDown(self):
        self.log_cfg = None

    def test_formatters(self):
        default = self.log_cfg.default_formatter
        assert default.datefmt == '%Y-%b-%d %H:%M:%S'
        assert default._fmt == '[%(asctime)s][%(name)s][%(levelname)s] %(message)s'

        blank = self.log_cfg.blank_formatter
        assert blank.datefmt is None
        assert blank._fmt == '%(message)s'

        assert self.log_cfg.formatter is default

        assert self.log_cfg.handlers == set()
        assert self.log_cfg.log_level == logging.INFO

    def test_get_logger(self):
        l = self.log_cfg.get_logger('a_logger')
        assert l.level == self.log_cfg.log_level
        assert l in self.log_cfg.loggers.values()
        assert list(self.log_cfg.handlers) == l.handlers

    def test_add_handler(self):
        h = logging.StreamHandler(stream=sys.stdout)
        self.log_cfg.add_handler(h)

        assert h in self.log_cfg.handlers
        assert h.formatter is self.log_cfg.formatter
        assert h.level == logging.INFO

    def test_set_log_level(self):
        h = logging.StreamHandler(stream=sys.stdout)
        self.log_cfg.add_handler(h, level=logging.INFO)
        l = self.log_cfg.get_logger('a_logger')
        assert h.level == l.level == logging.INFO

        self.log_cfg.set_log_level(logging.DEBUG)
        assert h.level == l.level == logging.DEBUG

    def test_set_formatter(self):
        h = logging.StreamHandler(stream=sys.stdout)
        self.log_cfg.add_handler(h)

        self.log_cfg.set_formatter(self.log_cfg.blank_formatter)
        assert h.formatter is self.log_cfg.blank_formatter
        self.log_cfg.set_formatter(self.log_cfg.default_formatter)
        assert h.formatter is self.log_cfg.default_formatter

    def test_configure_handlers_from_config(self):
        test_log = os.path.join(self.assets_path, 'test.log')
        self.log_cfg.configure_handlers_from_config()
        for h in self.log_cfg.handlers:
            if type(h) is logging.StreamHandler:
                assert h.stream is sys.stdout and h.level == logging.DEBUG
            elif type(h) is logging.FileHandler:
                assert h.stream.name == test_log and h.level == logging.WARNING
            elif type(h) is logging.handlers.TimedRotatingFileHandler:
                assert h.stream.name == test_log and h.level == logging.INFO
                assert h.when == 'H' and h.interval == 3600  # casts 'h' to 'H' and multiplies when to seconds


class TestAppLogger(app_logging.AppLogger, TestEGCG):
    def setUp(self):
        self.log_cfg = app_logging.logging_default
        app_logging.logging_default.add_stdout_handler(logging.DEBUG)

    def tearDown(self):
        app_logging.logging_default.handlers.clear()
        app_logging.logging_default.add_stdout_handler(logging.DEBUG)

    def test_log_msgs(self):
        self.debug('Debug')
        self.info('Info')
        self.warning('Warning')
        self.error('Error')
        self.critical('Critical')

    def test_get_logger(self):
        logger = self.log_cfg.get_logger('test')
        assert logger.level == self.log_cfg.log_level
        assert list(self.log_cfg.handlers) == logger.handlers
