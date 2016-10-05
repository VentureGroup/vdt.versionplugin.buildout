# coding: utf-8
from setuptools import find_packages, setup

pkgname = "vdt.versionplugin.buildout"

setup(name=pkgname,
      version="1.0.0",
      description="Version Increment Plugin that builds with debianize",
      author="CSI",
      author_email="csi@avira.com",
      maintainer="CSI",
      maintainer_email="csi@avira.com",
      packages=find_packages(),
      include_package_data=True,
      namespace_packages=['vdt', 'vdt.versionplugin'],
      zip_safe=True,
      install_requires=[
          "setuptools",
          "vdt.version",
          "vdt.versionplugin.default",
          "vdt.versionplugin.debianize>=1.0.4",
          "vdt.versionplugin.wheel",
          "mock",
          "setupreader"
      ],
      entry_points={},
      )
