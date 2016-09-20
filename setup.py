from setuptools import setup, find_packages

__version__ = "0.3.0.dev4"

setup(
    name="canopen",
    url="https://github.com/christiansandberg/canopen",
    version=__version__,
    packages=find_packages(),
    author="Christian Sandberg",
    author_email="christiansandberg@me.com",
    description="CANopen stack implementation",
    keywords="CAN CANopen",
    long_description=open("README.rst").read(),
    license="MIT",
    platforms=["any"],
    install_requires=["python-can", "canmatrix"],

    # Tests can be run using `python setup.py test`
    test_suite="nose.collector",
    tests_require=["nose"]
)
