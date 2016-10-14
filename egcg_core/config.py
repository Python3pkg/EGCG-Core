from os import getenv
from os.path import isfile
import yaml
from .exceptions import ConfigError


class Configuration:
    config_file = None
    content = {}

    def __init__(self, *search_path):
        if search_path:
            self.load_config_file(self._find_config_file(search_path))

    @staticmethod
    def _find_config_file(search_path):
        for p in search_path:
            if p and isfile(p):
                return p

    def load_config_file(self, *search_path):
        self.config_file = self._find_config_file(search_path)
        if self.config_file:
            self.content = yaml.safe_load(open(self.config_file, 'r'))
        else:
            raise ConfigError('Could not find any config file in specified search path')

    def get(self, item, ret_default=None):
        """
        Dict-style item retrieval with default
        :param item: The key to search for
        :param ret_default: What to return if the key is not present
        """
        try:
            return self[item]
        except KeyError:
            return ret_default

    def query(self, *parts, top_level=None, ret_default=None):
        """
        Drill down into a config, e.g. cfg.query('logging', 'handlers', 'a_handler', 'level')
        :param dict top_level:
        :param ret_default:
        :return: The relevant item if it exists in the config, else ret_default.
        """
        if top_level is None:
            top_level = self.content
        item = None

        for p in parts:
            item = top_level.get(p)
            if item:
                top_level = item
            else:
                return ret_default

        return item

    def report(self):
        return yaml.safe_dump(self.content, default_flow_style=False)

    def __getitem__(self, item):
        """Allow dict-style access, e.g. config['this'] or config['this']['that']."""
        return self.content[item]

    def __contains__(self, item):
        """Allow search in the first layer of the config with 'in' operator."""
        return self.content.__contains__(item)


class EnvConfiguration(Configuration):
    def __init__(self, *search_path, env_var='EGCGENV'):
        self.env_var = env_var
        super().__init__(*search_path)

    def load_config_file(self, *search_path, env_var=None):
        if env_var is not None:
            self.env_var = env_var
        super().load_config_file(*search_path)
        self._select_env()

    def _select_env(self):
        if not self.content.get('default'):
            raise ConfigError("Could not find 'default' environment in " + self.config_file)
        elif self.content:
            env = getenv(self.env_var, 'default')
            self.content = dict(self._merge_dicts(self.content['default'], self.content[env]))

    @classmethod
    def _merge_dicts(cls, default_dict, override_dict):
        """Recursively merge a default dict and an overriding dict."""
        for k in set(override_dict.keys()).union(default_dict.keys()):
            if k in default_dict and k in override_dict:
                if type(default_dict[k]) is dict and type(override_dict[k]) is dict:
                    yield k, dict(cls._merge_dicts(default_dict[k], override_dict[k]))
                else:
                    yield k, override_dict[k]
            elif k in default_dict:
                yield k, default_dict[k]
            else:
                yield k, override_dict[k]

    def merge(self, override_dict):
        """
        Merge the provided dict with the config content, potentially overriding existing parameters
        :param dict override_dict:
        """
        self.content = dict(self._merge_dicts(self.content, override_dict))

cfg = EnvConfiguration()
