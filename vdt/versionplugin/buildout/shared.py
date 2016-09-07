import os
import functools
import logging
import glob
import ConfigParser
import subprocess
import setupreader

import mock
from pip.req import RequirementSet
from pip._vendor import pkg_resources

from vdt.version.utils import change_directory
from vdt.versionplugin.debianize.shared import (
    PackageBuilder,
    DebianizeArgumentParser
)

from vdt.versionplugin.debianize.config import PACKAGE_TYPE_CHOICES


PIN_MARKS = {
    'equal': "==",
    'gte': ">="
}


log = logging.getLogger(__name__)


class BuildoutArgumentParser(DebianizeArgumentParser):
    "Build packages from python eggs with the same versions as pinned in buildout"

    def get_parser(self):
        p = super(BuildoutArgumentParser, self).get_parser()
        p.add_argument('--versions-file', help='Buildout versions.cfg')
        p.add_argument('--iteration', help="The iteration number for a hotfix")

        p.add_argument(
            '--pin-exact', action="store_const", const="equal",
            help="Pin exact versions in the generated debian control file, "
                 "including dependencies of dependencies.",
            dest="pin_versions")
        p.add_argument(
            '--pin-greater-or-equal', action="store_const", const="gte",
            help="Pin greater and equal versions in the generated debian"
                 "control file, including dependencies of dependencies.",
            dest="pin_versions")

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

    def requirement_versions(self):
        versions = {}
        for install_req in self.requirements.values():
            # when comes_from is not set it is a dependency to ourselves. So
            # skip that
            if install_req.comes_from:
                versions[install_req.name] = install_req.req.specs[0][1]
        return versions


def build_from_python_source_with_wheel(
        args, extra_args, target_path=None, version=None, file_name=None):
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


def write_requirements_txt(
        directory, pinned_requirements, specs_requirements, pin_mark="=="):
    requirements_txt = os.path.join(directory, "requirements.txt")
    result = []
    for package, version in pinned_requirements.items():
        if package in specs_requirements:
            result.append(specs_requirements[package])
        else:
            result.append("%s%s%s" % (package, pin_mark, version))
    with open(requirements_txt, "wb") as f:
        f.write("\n".join(result))


def delete_requirements_txt(directory):
    requirements_txt = os.path.join(directory, "requirements.txt")
    if os.path.exists(requirements_txt):
        os.remove(requirements_txt)


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

    def build_package(self, version, args, extra_args):
        if self.args.pin_versions:
            # we want the exact versions from our downloaded requirement_set
            # so let's create a requirements.txt file and say to FPM to use it
            downloaded_requirements = \
                self.downloaded_req_set.requirement_versions()

            # however, when we specify a version in setup_py,
            # we want to use that one
            setup_py = setupreader.load('setup.py')
            package_requirements = list(pkg_resources.parse_requirements(
                setup_py['install_requires']))

            # when 'specs' is defined, we have a dependency specified (>=1.0.0)
            specs_requirements = {
                x.project_name: x.__str__() for x in package_requirements if x.specs}  # noqa

            write_requirements_txt(
                self.directory, downloaded_requirements, specs_requirements,
                PIN_MARKS[self.args.pin_versions])

            extra_args.append("--python-obey-requirements-txt")

        super(PinnedVersionPackageBuilder, self).build_package(
            version, args, extra_args)

        if self.args.pin_versions:
            # cleanup
            delete_requirements_txt(self.directory)

    def build_dependency(self, args, extra_args, path, package_dir, deb_dir, glob_pattern=None, dependency_builder=None):
        if args.target == 'wheel':
            dependency_builder = build_from_python_source_with_wheel
            glob_pattern = "*.whl"

        super(PinnedVersionPackageBuilder, self).build_dependency(
            args, extra_args, path, package_dir, deb_dir, glob_pattern,
            dependency_builder)
