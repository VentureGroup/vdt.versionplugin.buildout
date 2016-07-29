import os
import functools
import logging
import glob
import ConfigParser
import subprocess
import shutil

import mock
from pip.req import RequirementSet, InstallRequirement
from pip._vendor import pkg_resources

from vdt.version.utils import change_directory
from vdt.versionplugin.debianize.shared import (
    PackageBuilder,
    DebianizeArgumentParser
)

from vdt.versionplugin.debianize.config import PACKAGE_TYPE_CHOICES


log = logging.getLogger(__name__)


class BuildoutArgumentParser(DebianizeArgumentParser):
    "Build packages from python eggs with the same versions as pinned in buildout"

    def get_parser(self):
        p = super(BuildoutArgumentParser, self).get_parser()
        p.add_argument('--versions-file', help='Buildout versions.cfg')
        p.add_argument('--iteration', help="The iteration number for a hotfix")
        # override this so we accept wheels
        p.add_argument(
            '--target', '-t', default='deb',
            choices=PACKAGE_TYPE_CHOICES + ["wheel"],
            help='the type of package you want to create (deb, rpm, etc)')
        return p


def delete_old_packages():
    log.debug(">> Deleting old packages:")
    log.debug(glob.glob('*.deb'))
    for package in glob.glob('*.deb'):
        os.remove(package)


def parse_version_extra_args(version_args):
    parser = BuildoutArgumentParser(version_args)
    return parser.parse_known_args()


def lookup_versions(versions_file):
    versions_config = ConfigParser.ConfigParser()
    versions_config.read(versions_file)
    return dict(versions_config.items('versions'))


class PinnedRequirementSet(RequirementSet):
    def __init__(self, versions, file_filter, *args, **kwargs):
        self.versions = versions
        self.file_filter = file_filter
        super(PinnedRequirementSet, self).__init__(*args, **kwargs)

    def add_requirement(self, install_req, parent_req_name=None):
        name = install_req.name.lower() if install_req.name else None
        if name in self.versions:
            pinned_version = "%s==%s" % (name, self.versions.get(name))
            install_req.req = pkg_resources.Requirement.parse(pinned_version)
        if name and self.file_filter.is_filtered(name):
            return []
        return super(PinnedRequirementSet, self).add_requirement(
            install_req, parent_req_name)


def build_from_python_source_with_wheel(args, extra_args, target_path=None, version=None, file_name=None):
    target_wheel_dir = os.path.join(os.getcwd(), 'dist')
    with change_directory(target_path):
        try:
            cmd = ['pip', 'wheel', '.', '--no-deps', '--wheel-dir', target_wheel_dir]  # noqa
            log.debug("Running command {0}".format(" ".join(cmd)))
            log.debug(subprocess.check_output(cmd, cwd=target_path))
        except subprocess.CalledProcessError as e:
            log.error("failed to build with wheel status code %s\n%s" % (
                e.returncode, e.output
            ))
            return 1


class PinnedVersionPackageBuilder(PackageBuilder):
    def download_dependencies(self, install_dir, deb_dir):
        versions = lookup_versions(self.args.versions_file)
        # we have a file filter in the PackageBuilder, so we can skip the
        # download if we want to
        foo = functools.partial(
            PinnedRequirementSet, versions, self.file_filter)
        with mock.patch('pip.commands.download.RequirementSet', foo):
            return super(
                PinnedVersionPackageBuilder, self).download_dependencies(
                    install_dir, deb_dir)

    def build_dependency(self, args, extra_args, path, package_dir, deb_dir, glob_pattern=None, dependency_builder=None):
        if args.target == 'wheel':
            dependency_builder = build_from_python_source_with_wheel
            glob_pattern = "*.whl"

        super(PinnedVersionPackageBuilder, self).build_dependency(
            args, extra_args, path, package_dir, deb_dir, glob_pattern, dependency_builder)
