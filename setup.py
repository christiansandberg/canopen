from setuptools import setup, find_packages

description = open("README.rst").read()
# Change links to stable documentation
description = description.replace("/latest/", "/stable/")

setup(
    name="canopen",
    url="https://github.com/christiansandberg/canopen",
    use_scm_version=True,
    packages=find_packages(),
    author="Christian Sandberg",
    author_email="christiansandberg@me.com",
    description="CANopen stack implementation",
    keywords="CAN CANopen",
    long_description=description,
    license="MIT",
    platforms=["any"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering"
    ],
    install_requires=["python-can>=3.0.0"],
    extras_require={
        "db_export": ["canmatrix"]
    },
    setup_requires=["setuptools_scm"],
    include_package_data=True
)
