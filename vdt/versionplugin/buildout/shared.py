import os
import string
import argparse
import ConfigParser
import imp
import logging
import tempfile
import shutil
import pip
import subprocess
import glob
from mock import patch

log = logging.getLogger('vdt.versionplugin.buildout.package')

broken_scheme_names = {'pyyaml': 'yaml',
                       'pyzmq': 'zmq'}


def build_dependent_packages():
    log.debug(">> Building dependent packages:")
    tmp_dir = tempfile.mkdtemp()
    try:
        pip.main(['install', '--upgrade', '--no-install', '--build=' + tmp_dir, '--editable', '.'])
        for pkg_name in os.listdir(tmp_dir):
            fpm_cmd = fpm_command(pkg_name, os.path.join(tmp_dir, pkg_name, 'setup.py'))

            log.debug("Running command {0}".format(" ".join(fpm_cmd)))
            log.debug(subprocess.check_output(fpm_cmd))
    finally:
        shutil.rmtree(tmp_dir)


def fpm_command(pkg_name, setup_py, no_python_dependencies=False, extra_args=None):
    fpm_cmd = ['fpm']
    if pkg_name.lower() in broken_scheme_names:
        fpm_cmd += ['-n', 'python-' + broken_scheme_names[pkg_name.lower()]]

    pre_remove_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files/preremove')
    fpm_cmd += ['-s', 'python', '-t', 'deb', '--maintainer=CSI', '--exclude=*.pyc',
                '--exclude=*.pyo', '--depends=python', '--category=python',
                '--template-scripts', '--python-install-lib=/usr/lib/python2.7/dist-packages/',
                '--before-remove=' + pre_remove_script]
    if no_python_dependencies:
        fpm_cmd += ['--no-python-dependencies']

    if extra_args:
        fpm_cmd += extra_args + [setup_py]
    else:
        fpm_cmd += [setup_py]

    return fpm_cmd


def delete_old_packages():
    log.debug(">> Deleting old packages:")
    log.debug(glob.glob('*.deb'))
    for package in glob.glob('*.deb'):
        os.remove(package)


def read_dependencies(file_name='setup.py'):
    dependencies = []
    log.debug(">> Reading dependencies:")
    with patch('setuptools.setup') as setup_mock, patch('setuptools.find_packages') as _:
        imp.load_source('setup', file_name)

        for dependency in setup_mock.call_args[1]['install_requires']:
            dependencies.append(string.lower(dependency))
    log.debug(dependencies)
    return dependencies


def extend_extra_args(extra_args, dependencies_with_versions):
    log.debug(">> Extending extra args:")
    for pkg_name, version in dependencies_with_versions.iteritems():
        if pkg_name in broken_scheme_names:
            pkg_name = broken_scheme_names[pkg_name]

        if version:
            arg = '"python-' + pkg_name + " = " + version + '"'
        else:
            arg = 'python-' + pkg_name
        extra_args.append('-d')
        extra_args.append(arg)
    log.debug(extra_args)
    return extra_args


def lookup_versions(dependencies, versions_file):
    log.debug(">> Lookup versions:")
    dependencies_with_versions = {}
    versions_config = ConfigParser.ConfigParser()
    versions_config.read(versions_file)

    for dependency in dependencies:
        if versions_config.has_option('versions', dependency):
            dependencies_with_versions[dependency] = versions_config.get('versions', dependency)
        else:
            dependencies_with_versions[dependency] = None
    log.debug(dependencies_with_versions)
    return dependencies_with_versions


def parse_version_extra_args(version_args):
    parser = argparse.ArgumentParser(description="Package python packages with debianize.sh.")
    parser.add_argument('--include',
                        '-i',
                        action='append',
                        help="Using this flag makes following dependencies explicit. It will only"
                             " build dependencies listed in install_requires that match the regex"
                             " specified after -i. Use -i multiple times to specify"
                             " multiple packages")
    parser.add_argument('--versions-file', help='Buildout versions.cfg')
    args, extra_args = parser.parse_known_args(version_args)
    
    return args, extra_args