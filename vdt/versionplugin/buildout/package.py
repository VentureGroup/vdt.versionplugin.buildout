import logging
import subprocess
import os

from vdt.versionplugin.buildout.shared import parse_version_extra_args
from vdt.versionplugin.buildout.shared import read_dependencies
from vdt.versionplugin.buildout.shared import lookup_versions
from vdt.versionplugin.buildout.shared import extend_extra_args
from vdt.versionplugin.buildout.shared import build_dependent_packages
from vdt.versionplugin.buildout.shared import fpm_command
from vdt.versionplugin.buildout.shared import delete_old_packages

log = logging.getLogger('vdt.versionplugin.buildout.package')


def build_package(version):
    """
    Build package with debianize.
    """
    args, extra_args = parse_version_extra_args(version.extra_args)
    dependencies = read_dependencies()
    dependencies_with_versions = lookup_versions(dependencies, args.versions_file)
    extra_args = extend_extra_args(extra_args, dependencies_with_versions)
    delete_old_packages()

    log.debug("Building {0} version {1} with "
              "vdt.versionplugin.buildout".format(os.path.basename(os.getcwd()), version))
    with version.checkout_tag:
        fpm_cmd = fpm_command(os.path.basename(os.getcwd()), 'setup.py',
                              no_python_dependencies=True, extra_args=extra_args, version=version)

        log.debug("Running command {0}".format(" ".join(fpm_cmd)))
        log.debug(subprocess.check_output(fpm_cmd))
        build_dependent_packages()

    return 0


def set_package_version(version):
    """
    If there need to be modifications to source files before a
    package can be built (changelog, version written somewhere etc.)
    that code should go here
    """
    log.debug("set_package_version is not implemented for vdt.versionplugin.buildout")
    if version.annotated and version.changelog and version.changelog != "":
        "modify setup.py and write the version"
        log.debug("got an annotated version, should modify setup.py")
