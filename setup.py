from setuptools import setup, find_packages

# To use a consistent encoding
from codecs import open
from os import path

# The directory containing this file
HERE = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(HERE, 'README.rst'), encoding='utf-8') as f:
    readme_content = f.read()

# This call to setup() does all the work
setup(
    name='canopen',
    packages=find_packages(),
    version='2.1.0',
    description='CANopen stack implementation',
    long_description=readme_content,
    long_description_content_type='text/markdown',
    author='Christian Sandberg',
    license='MIT',
    install_requires=['can'],
)
