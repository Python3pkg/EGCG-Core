from setuptools import setup, find_packages
from os.path import join, abspath, dirname
from egcg_core import __version__
requirements_txt = join(abspath(dirname(__file__)), 'requirements.txt')
requirements = [l.strip() for l in open(requirements_txt) if l and not l.startswith('#')]


def _translate_req(r):
    # this>=0.3.2 -> this(>=0.3.2)
    ops = ('<=', '>=', '==', '<', '>', '!=')
    version = None
    for op in ops:
        if op in r:
            r, version = r.split(op)
            version = op + version

    req = r
    if version:
        req += '(%s)' % version
    return req


setup(
    name='EGCG-Core',
    version=__version__,
    packages=find_packages(exclude=('tests',)),
    url='https://github.com/EdinburghGenomics/EGCG-Core',
    license='MIT',
    description='Shared functionality across EGCG projects',
    long_description='Common modules for use across EGCG projects. Includes logging, configuration, common '
                     'exceptions, random utility functions, and modules for interfacing with external data '
                     'sources such as EGCG\'s reporting app and Clarity LIMS instance',
    requires=[_translate_req(r) for r in requirements],  # metadata
    install_requires=requirements  # actual module requirements
)
