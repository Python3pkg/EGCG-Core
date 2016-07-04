import json
import os.path
import unittest
from unittest.mock import Mock


class FakeRestResponse(Mock):
    def __init__(self, *args, **kwargs):
        content = kwargs.pop('content', None)
        if type(content) in (list, dict):
            content = json.dumps(content)
        content = content.encode()
        super().__init__(*args, **kwargs)
        self.content = content
        self.request = Mock(method='a method', path_url='a url')
        self.status_code = 200
        self.reason = 'a reason'

    def json(self):
        return json.loads(self.content.decode('utf-8'))

    @property
    def text(self):
        return self.content.decode('utf-8')


class TestEGCG(unittest.TestCase):
    file_path = os.path.dirname(__file__)
    assets_path = os.path.join(file_path, 'assets')

    etc = os.path.join(os.path.dirname(file_path), 'etc')
    etc_config = os.path.join(etc, 'example_egcg.yaml')

    @staticmethod
    def compare_lists(observed, expected):
        if sorted(observed) != sorted(expected):
            print('')
            print('observed')
            print(observed)
            print('expected')
            print(expected)
            raise AssertionError
