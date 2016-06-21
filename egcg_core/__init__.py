from os.path import join, dirname, abspath
__version__ = open(join(dirname(dirname(abspath(__file__))), 'version.txt')).read().strip().lstrip('v')
