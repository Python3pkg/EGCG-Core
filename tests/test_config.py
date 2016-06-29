import os
import pytest
from tests import TestEGCG
from egcg_core.config import EnvConfiguration
from egcg_core.exceptions import EGCGError


class TestConfiguration(TestEGCG):
    def setUp(self):
        self.cfg = EnvConfiguration(
            (
                os.getenv('EGCGCONFIG'),
                os.path.join(self.assets_path, '..', '..', 'etc', 'example_egcg.yaml')
            )
        )

    def test_get(self):
        get = self.cfg.get
        assert get('nonexistent_thing') is None
        assert get('nonexistent_thing', 'a_default') == 'a_default'
        assert self.cfg.get('executor').get('job_execution') == 'local'

    def test_find_config_file(self):
        existing_cfg_file = os.path.join(self.assets_path, '..', '..', 'etc', 'example_egcg.yaml')
        non_existing_cfg_file = os.path.join(self.assets_path, 'a_file_that_does_not_exist.txt')
        assert self.cfg._find_config_file((non_existing_cfg_file, existing_cfg_file)) == existing_cfg_file

        self.cfg.content = None
        self.cfg._find_config_file((non_existing_cfg_file,))
        assert self.cfg.content is None

    def test_query(self):
        assert self.cfg.query('executor', 'job_execution') == 'local'
        assert self.cfg.query('nonexistent_thing') is None
        assert self.cfg.query('logging', 'handlers', 'nonexistent_handler') is None
        assert self.cfg.query('logging') == {
            'stream_handlers': [{'stream': 'ext://sys.stdout', 'level': 'DEBUG'}],
            'file_handlers': [{'filename': 'tests/assets/test.log', 'mode': 'a', 'level': 'WARNING'}],
            'timed_rotating_file_handlers': [{'filename': 'tests/assets/test.log', 'when': 'h', 'interval': 1}],
            'datefmt': '%Y-%b-%d %H:%M:%S',
            'format': '[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
        }

    def test_merge_dicts(self):
        default_dict = {
            'this': {
                'another': [2, 3, 4],
                'more': {
                    'thing': 'thang'
                }
            },
            'that': 'a_thing',
            'other': {
                'another': [2, '3', 4],
                'more': {
                    'thing': 'thang'
                }
            }
        }
        override_dict = {
            'that': 'another_thing',
            'another': 4,
            'more': 5,
            'other': {
                'another': [8, 9, 10],
                'more': {'thung': 'theng'}
            }
        }
        merged_dict = self.cfg._merge_dicts(default_dict, override_dict)

        assert dict(merged_dict) == {
            'this': {
                'another': [2, 3, 4],
                'more': {
                    'thing': 'thang'
                }
            },
            'that': 'another_thing',
            'other': {
                'another': [8, 9, 10],
                'more': {
                    'thing': 'thang',
                    'thung': 'theng'
                }
            },
            'another': 4,
            'more': 5
        }

        assert dict(self.cfg._merge_dicts(default_dict, default_dict)) == default_dict
