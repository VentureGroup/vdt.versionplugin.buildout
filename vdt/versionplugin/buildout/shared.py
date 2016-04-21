import os
import argparse
import ConfigParser
import imp
import logging
import pip
import subprocess
import glob
from mock import patch
import sys
import json

log = logging.getLogger('vdt.versionplugin.buildout.package')

broken_scheme_names = {'pyyaml': 'yaml',
                       'pyzmq': 'zmq',
                       'pycrypto': 'crypto',
                       'yaml': 'pyyaml',
                       'zmq': 'pyzmq',
                       'crypto': 'pycrypto',
                       'python-debian': 'debian',
                       'python-dateutil': 'dateutil'}


def traverse_dependencies(deps_with_versions, versions_file):
    nested_deps_with_version = build_dependent_packages(deps_with_versions, versions_file)

    if nested_deps_with_version:
        traverse_dependencies(nested_deps_with_version, versions_file)


def download_package(dependency, version, download_dir):
    if version:
        pip_args = dependency + '==' + version
    else:
        pip_args = dependency

    pip.main(['install', '-q', pip_args, '--ignore-installed', '--download=' + download_dir])


def build_with_fpm(package_name, setup_py=None, extra_args=None, version=None, no_python_dependencies=True):
    fpm_cmd = fpm_command(package_name, setup_py, no_python_dependencies=no_python_dependencies,
                          extra_args=extra_args, version=version)
    log.debug("Running command {0}".format(" ".join(fpm_cmd)))
    fpm_output = subprocess.check_output(fpm_cmd)
    log.debug(fpm_output)
    return fpm_output


def ruby_to_json(ruby_hash):
    ruby_command = ['ruby', '-e', 'require "json"; puts JSON.generate(%s)' % ruby_hash.rstrip()]
    return json.loads(subprocess.check_output(ruby_command))


def parse_from_dpkg_output(dpkg_output):
    debian_dependencies = dpkg_output.replace('(', '').replace(')', '').split(',')
    return debian_dependencies


def read_dependencies_package(package_name):
    dpkg_output = subprocess.check_output(['dpkg', '-f', package_name, 'Depends'])

    debian_dependencies = parse_from_dpkg_output(dpkg_output)

    python_dependencies = []
    for dependency in debian_dependencies:
        dependency = dependency.split('==')[0].split('<=')[0].split('<<')[0].split('>=')[0].split('>>')[0].split('!=')[0].split('=')[0]
        dependency = dependency.strip().lower()
        if dependency != 'python':
            dependency = dependency.lower().replace('python-', '')
            python_dependencies.append(dependency)
    return python_dependencies


def build_dependent_packages(deps_with_versions, versions_file):
    log.debug(">> Building dependent packages:")
    nested_deps_with_version = []
    for package_name, version in deps_with_versions:
        try:
            fpm_output = build_with_fpm(package_name, version=version, no_python_dependencies=False)
            json_output = ruby_to_json(fpm_output)
            python_dependencies = read_dependencies_package(json_output['path'])

            if python_dependencies:
                temp_deps_with_versions = lookup_versions(python_dependencies, versions_file)
                # we have to build the package two times
                # first time: get dependencies
                # second time: build with fixed name scheme and correct versions
                extra_args = create_fpm_extra_args(fix_dependencies(temp_deps_with_versions))

                build_with_fpm(package_name, extra_args=extra_args,
                               version=version, no_python_dependencies=True)

                for dep_with_version in temp_deps_with_versions:
                    if dep_with_version not in nested_deps_with_version:
                        nested_deps_with_version.append(dep_with_version)
        except subprocess.CalledProcessError as error:
            pass

    return nested_deps_with_version


def download_bdist_dependencies(deps_with_versions):
    for package_name, version in deps_with_versions:
        download_package(package_name, version, os.getcwd())


def build_bdist():
    dist_cmd = ['python', 'setup.py', 'bdist_wheel', '--dist-dir=' + os.getcwd()]
    log.debug("Running command {0}".format(" ".join(dist_cmd)))
    dist_cmd_output = subprocess.check_output(dist_cmd)
    log.debug(dist_cmd_output)


def fpm_command(pkg_name, setup_py=None, no_python_dependencies=False, extra_args=None, version=None, iteration=0):
    fpm_cmd = ['fpm']
    if pkg_name.lower() in broken_scheme_names:
        fpm_cmd += ['--name', 'python-' + broken_scheme_names[pkg_name.lower()]]

    if version:
        if iteration:
            version = '%s.%s' % (version, iteration)
        fpm_cmd += ['--version=%s' % version]

    pre_remove_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files/preremove')
    fpm_cmd += ['-s', 'python', '-t', 'deb', '-f', '--maintainer=CSI', '--exclude=*.pyc',
                '--exclude=*.pyo', '--depends=python', '--category=python',
                '--python-bin=/usr/bin/python', '--template-scripts',
                '--python-install-lib=/usr/lib/python2.7/dist-packages/',
                '--deb-no-default-config-files',
                '--python-install-bin=/usr/local/bin/', '--before-remove=' + pre_remove_script]
    if no_python_dependencies:
        fpm_cmd += ['--no-python-dependencies']

    if extra_args:
        fpm_cmd += extra_args

    if setup_py:
        fpm_cmd += [setup_py]
    else:
        fpm_cmd += [pkg_name]

    return fpm_cmd


def delete_old_packages():
    log.debug(">> Deleting old packages:")
    log.debug(glob.glob('*.deb'))
    for package in glob.glob('*.deb'):
        os.remove(package)


def read_dependencies_setup_py(file_name):
    log.debug(">> Reading dependencies from %s:" % file_name)
    with patch('setuptools.setup') as setup_mock, patch('setuptools.find_packages'),\
    patch('distutils.core.setup'):
        _load_module(file_name)
        dependencies = strip_dependencies(setup_mock)
    
    log.debug(dependencies)
    return dependencies


def strip_dependencies(setup_mock):
    try:
        dependencies = []
        for dep in setup_mock.call_args[1]['install_requires']:
            dep = dep.split('==')[0].split('<=')[0].split('>=')[0].split('!=')[0]
            dep = dep.strip().lower()
            dependencies.append(dep)
    except:
        # we are only interested in ['install_requires']
        pass
    return dependencies


def _load_module(file_name):
    # in order to load setup.py we need to change working dir and add it to sys path
    log.debug(">> Loading module")
    old_wd = os.getcwd()
    new_wd = os.path.dirname(file_name)
    os.chdir(new_wd)
    sys.path.insert(0, new_wd)
    try:
        imp.load_source('setup', file_name)
    except SystemExit and IOError:
        # make sure nobody kills the package builder
        pass
    finally:
        os.chdir(old_wd)


def fix_dependencies(dependencies_with_versions):
    fixed_dependencies_with_versions = []
    for pkg_name, version in dependencies_with_versions:
        if pkg_name in broken_scheme_names:
            fixed_dependencies_with_versions.append((broken_scheme_names[pkg_name], version))
        else:
            fixed_dependencies_with_versions.append((pkg_name, version))
    return fixed_dependencies_with_versions


def create_fpm_extra_args(dependencies_with_versions, existing_extra_args=None):
    log.debug(">> Extending extra args:")
    if existing_extra_args:
        extra_args = existing_extra_args
    else:
        extra_args = []
    for pkg_name, version in dependencies_with_versions:
        if version:
            arg = 'python-' + pkg_name + ' >= ' + version
        else:
            arg = 'python-' + pkg_name

        extra_args.append('-d')
        extra_args.append(arg)
    log.debug(extra_args)
    return extra_args


def lookup_versions(dependencies, versions_file):
    log.debug(">> Lookup versions:")
    dependencies_with_versions = []
    versions_config = ConfigParser.ConfigParser()
    versions_config.read(versions_file)

    for dependency in dependencies:
        if versions_config.has_option('versions', dependency):
            dependencies_with_versions.append((dependency, versions_config.get('versions', dependency)))
        else:
            dependencies_with_versions.append((dependency, None))
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
    parser.add_argument('--iteration', help="The iteration number for a hotfix")
    parser.add_argument('--bdist',
                        help="Creates an additional source distribution and its dependencies",
                        action='store_true',
                        default=False)
    args, extra_args = parser.parse_known_args(version_args)
    
    return args, extra_args