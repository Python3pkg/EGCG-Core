from distutils.core import setup
from os.path import join, abspath, dirname
requirements = join(abspath(dirname(__file__)), 'requirements.txt')

setup(
    name='EGCG-Core',
    version='0.1',
    packages=['egcg_core', 'egcg_core.executor', 'egcg_core.executor.script_writers'],
    url='http://genomics.ed.ac.uk',
    license='',
    author='mwhamgenomics',
    author_email='',
    description='Common modules for use across EGCG projects. Includes logging, configuration, common '
                'exceptions, random utility functions, and modules for interfacing with external data '
                'sources such as EGCG\'s reporting app and Clarity LIMS instance',
    requires=[l for l in open(requirements).readlines() if l and not l.startswith('#')]
)
