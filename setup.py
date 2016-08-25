from setuptools import setup, find_packages

__version__ = "0.1.0"

setup(
    name="canopen",
    url="https://bitbucket.org/evs-inmotion/canopen",
    version=__version__,
    packages=find_packages(),
    author="Christian Sandberg",
    author_email="christian.sandberg@evs-inmotion.com",
    description="CANopen stack implementation",
    keywords="CAN CANopen",
    long_description=open("README.rst").read(),
    #license="LGPL v3",
    platforms=["any"],
    install_requires=["python-can"]
)
