"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='hedgehog-gui',
    version='0.2.1',
    description='GUI for visualizing and controlling Hedgehog robots',
    long_description=long_description,
    url="https://github.com/PRIArobotics/HedgehogGui",
    author="Clemens Koza",
    author_email="koza@pria.at",
    license="AGPLv3+",

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'Topic :: Software Development',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Programming Language :: Python :: 3',
    ],

    keywords='hedgehog robotics controller client gui',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['hedgehog-client', 'kivy', 'kivymd'],

    # You can install these using the following syntax, for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'test': ['hedgehog-server'],
    },

    package_data={
        'hedgehog.gui': ['*.kv'],
    },

    entry_points={
        'console_scripts': [
            'hedgehog-gui = hedgehog.gui:main',
        ],
    },
)
