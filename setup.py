#!/usr/bin/env python3

import os
import subprocess
from setuptools import setup, find_packages

from tempfile import TemporaryDirectory

with open('README.md') as readme_file:
    readme = readme_file.read()

setup(
    name='ctucan',
    description="Configurable CAN IP-core for LiteX SoC Builder",
    author="Antmicro",
    url='https://github.com/antmicro/ctucan',
    license="Apache Software License 2.0",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    zip_safe=False,
    long_description=readme,
    long_description_content_type="text/markdown",
    python_requires='>=3.6',
    install_requires=[
        'migen>=0.9.2',
        'litex>=0.0.0',
    ],
    keywords='LiteX CAN',
    packages=find_packages(include=['ctucan', 'ctucan.*']),
    package_dir={"ctucan": "ctucan"},
    package_data={'ctucan': ['vhdl/*.vhd']},
    include_package_data=True,
    version='0.1.0',
)
