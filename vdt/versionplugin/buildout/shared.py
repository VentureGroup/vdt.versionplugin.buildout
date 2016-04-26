import os
import functools
import logging
import glob
import ConfigParser

import mock
from pip.req import RequirementSet, InstallRequirement
from pip._vendor import pkg_resources

from vdt.versionplugin.debianize.shared import (
    PackageBuilder,
    DebianizeArgumentParser
)

log = logging.getLogger(__name__)


class BuildoutArgumentParser(DebianizeArgumentParser):
    "Build packages from python eggs with the same versions as pinned in buildout"

    def get_parser(self):
        p = super(BuildoutArgumentParser, self).get_parser()
        p.add_argument('--versions-file', help='Buildout versions.cfg')
        p.add_argument('--iteration', help="The iteration number for a hotfix")
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
    log.debug(dir(versions_config))
    log.debug(versions_config.items('versions'))
    return dict(versions_config.items('versions'))


class PinnedRequirementSet(RequirementSet):
    def __init__(self, versions, *args, **kwargs):
        self.versions = versions
        super(PinnedRequirementSet, self).__init__(*args, **kwargs)

    def add_requirement(self, install_req, parent_req_name=None):
        name = install_req.name
        if name in self.versions:
            pinned_version = "%s==%s" % (name, self.versions.get(name))
            install_req.req = pkg_resources.Requirement.parse(pinned_version)

        return super(PinnedRequirementSet, self).add_requirement(install_req, parent_req_name)


class PinnedVersionPackageBuilder(PackageBuilder):
    def download_dependencies(self, install_dir, deb_dir):
        versions = lookup_versions(self.args.versions_file)
        foo = functools.partial(PinnedRequirementSet, versions)
        with mock.patch('pip.commands.download.RequirementSet', foo):
            return super(PinnedVersionPackageBuilder, self).download_dependencies(install_dir, deb_dir)
