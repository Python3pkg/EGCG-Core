from setuptools import setup
from os.path import join, abspath, dirname
requirements_txt = join(abspath(dirname(__file__)), 'requirements.txt')

ops = ('<=', '>=', '==', '<', '>', '!=')


def _translate_req(r):
    # this>=0.3.2 -> this(>=0.3.2)
    version = None
    for o in ops:
        if o in r:
            r, version = r.split(o)
            version = o + version

    req = r
    if version:
        req += '(%s)' % version
    return req

requirements = [l.strip() for l in open(requirements_txt) if l and not l.startswith('#')]

setup(
    name='EGCG-Core',
    version='0.1',
    packages=['egcg_core', 'egcg_core.executor', 'egcg_core.executor.script_writers'],
    url='http://genomics.ed.ac.uk',
    license='MIT',
    description='Common modules for use across EGCG projects. Includes logging, configuration, common '
                'exceptions, random utility functions, and modules for interfacing with external data '
                'sources such as EGCG\'s reporting app and Clarity LIMS instance',
    requires=[_translate_req(r) for r in requirements],  # metadata
    install_requires=requirements  # actual module requirements
)
