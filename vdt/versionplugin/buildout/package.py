import logging
from os.path import basename
from os import getcwd

from vdt.versionplugin.buildout.shared import (
    parse_version_extra_args,
    PinnedVersionPackageBuilder,
    delete_old_packages
)


log = logging.getLogger(__name__)


def build_package(version):
    """
    Build package with debianize.
    """
    args, extra_args = parse_version_extra_args(version.extra_args)

    delete_old_packages()

    with version.checkout_tag:
        deb_dir = getcwd()

        if args.iteration is not None:
            version_string = "%s.%s" % (version, args.iteration)
        else:
            version_string = str(version)

        log.debug("Building {0} version {1} with "
              "vdt.versionplugin.buildout".format(basename(deb_dir), version_string))

        # use a package build class which has all kinds of hooks.
        builder = PinnedVersionPackageBuilder(version_string, args, extra_args, deb_dir)
        builder.build_package_and_dependencies()
        return builder.exit_code

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
