from setuptools import setup, find_packages

exec(open('canopen/version.py').read())

description = open("README.rst").read()
# Change links to stable documentation
description = description.replace("/latest/", "/stable/")
# Change pip install to this exact version
description = description.replace(
    "pip install canopen",
    "pip install canopen==" + __version__)

setup(
    name="canopen",
    url="https://github.com/christiansandberg/canopen",
    version=__version__,
    packages=find_packages(),
    author="Christian Sandberg",
    author_email="christiansandberg@me.com",
    description="CANopen stack implementation",
    keywords="CAN CANopen",
    long_description=description,
    license="MIT",
    platforms=["any"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering"
    ],
    install_requires=["python-can>=2.0.0"],
    extras_require={
        "db_export": ["canmatrix"]
    },
    include_package_data=True,

    # Tests can be run using `python setup.py test`
    test_suite="nose.collector",
    tests_require=["nose"]
)
