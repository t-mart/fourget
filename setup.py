import sys
import os

from setuptools import setup

setup(
    name = 'fourget',
    version = '0.0.1',
    author = 'Tim Martin',
    author_email = 'tim@timmart.in',
    description = ('download 4chan images'),
    license = 'MIT',
    url = 'http://github.com/t-mart/fourget',
    entry_points = {
    'console_scripts': [
        'fourget = fourget.run:run',
        ],
    },
    packages = [ 'fourget', ],
    install_requires = ['requests>=2.2.1', 'clint>=0.3.4'],
)
