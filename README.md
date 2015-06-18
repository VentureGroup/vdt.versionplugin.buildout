vdt.versionplugin.buildout
===========================

Plugin for https://github.com/devopsconsulting/vdt.version

This plugin uses [FPM](https://github.com/jordansissel/fpm/wiki) to build a Debian package out of
Python sources within the src folder of your [buildout](www.buildout.org). Additionally you will
get Debian packages for the whole dependency tree of your package. On doing so, all dependencies
are pinned to a minimum version in the control files of the resulting Debian packages. The versions
for the pinning are taken from the versions.cfg file of your buildout or any other file with the
same structure.

Some maintainers of packages do not stick to the correct naming scheme between their Python and
Debian packages:
- pyyaml   <-> python-yaml
- pyzmq    <-> python-zmq
- pycrypto <-> python-crypto

If you would build these packages with FPM you would end up with the following broken package names:
- pyyaml -> python-pyyaml
- pyzmq -> python-pyzmq
- pycrypto -> python-pycrypto

The vdt.versionplugin.buildout also takes care of this and fixes the affected names for you.

You can use this plugin the following way in your buildout:
    ```
    cd src/package-to-build
    ../../bin/version --plugin=buildout --versions-file=versions.cfg -v
    ```
