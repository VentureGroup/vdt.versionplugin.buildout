#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

version = '1.2.0'

setup(
    name='tag-hub',
    version=version,
    description="Task distribution and result aggregation",
    long_description="TAG hub distributes tasks to DetectionModules and aggregates results.",
    classifiers=[],
    keywords='',
    author='PSR',
    author_email='psr@avira.com',
    url='https://github.dtc.avira.com/APC/tag.hub',
    license='',
    packages=find_packages(exclude=['tag.hub.test']),
    namespace_packages=['tag'],
    include_package_data=True,
    zip_safe=False,
    install_requires=['setuptools',
                      'PyYAML',
                      'puka',
                      'couchbase'],
    entry_points={
        'console_scripts': [
            'tag-hub = tag.hub.main:main',
            'add-task-puka = utils.tasks_generator_puka:main'
        ]
    },
)