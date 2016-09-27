from setuptools import setup, find_packages

exec(open('canopen/version.py').read())

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
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering"
    ],
    install_requires=["python-can~=1.5.2", "canmatrix"],

    # Tests can be run using `python setup.py test`
    test_suite="nose.collector",
    tests_require=["nose"]
)
