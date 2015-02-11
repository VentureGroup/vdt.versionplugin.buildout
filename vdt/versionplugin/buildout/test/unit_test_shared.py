from mock import patch, call, Mock
import pytest
import os

from vdt.versionplugin.buildout.shared import delete_old_packages
from vdt.versionplugin.buildout.shared import build_dependent_packages
from vdt.versionplugin.buildout.shared import fpm_command
from vdt.versionplugin.buildout.shared import read_dependencies
from vdt.versionplugin.buildout.shared import extend_extra_args
from vdt.versionplugin.buildout.shared import lookup_versions
from vdt.versionplugin.buildout.shared import parse_version_extra_args


def test_delete_old_packages():
    test_glob = ['test-1.deb', 'test-2.deb', 'test-3.deb']
    with patch('vdt.versionplugin.buildout.shared.log'),\
            patch('vdt.versionplugin.buildout.shared.glob') as mock_glob,\
            patch('vdt.versionplugin.buildout.shared.os') as mock_os:

        mock_glob.glob.return_value = test_glob

        delete_old_packages()

        calls = [call.remove(glob) for glob in test_glob]
        mock_os.assert_has_calls(calls)


def test_build_dependent_packages():
    with patch('vdt.versionplugin.buildout.shared.log'),\
            patch('vdt.versionplugin.buildout.shared.tempfile') as mock_temp,\
            patch('vdt.versionplugin.buildout.shared.pip') as mock_pip,\
            patch('vdt.versionplugin.buildout.shared.fpm_command') as mock_fpm,\
            patch('vdt.versionplugin.buildout.shared.shutil') as mock_shutil,\
            patch('vdt.versionplugin.buildout.shared.subprocess') as mock_subprocess,\
            patch('vdt.versionplugin.buildout.shared.os.path') as mock_os_path:

            mock_temp.mkdtemp.return_value = '/home/test/'
            mock_fpm.return_value = 'fpm -s python -t deb'
            mock_os_path.exists.return_value = True

            build_dependent_packages({'pyyaml': '1.0.0', 'puka': None})

            calls = [call(['install', 'puka', '--ignore-installed', '--no-install',
                           '--build=' + mock_temp.mkdtemp.return_value]),
                     call(['install', 'pyyaml==1.0.0', '--ignore-installed', '--no-install',
                           '--build=' + mock_temp.mkdtemp.return_value])]
            mock_pip.main.assert_has_calls(calls)
            calls = [call('fpm -s python -t deb'), call('fpm -s python -t deb')]
            mock_subprocess.check_output.assert_has_calls(calls)
            mock_shutil.rmtree.assert_called_once_with(mock_temp.mkdtemp.return_value)


def test_build_dependent_packages_exception():
    with patch('vdt.versionplugin.buildout.shared.log'),\
            patch('vdt.versionplugin.buildout.shared.tempfile') as mock_temp,\
            patch('vdt.versionplugin.buildout.shared.pip') as mock_pip,\
            patch('vdt.versionplugin.buildout.shared.shutil') as mock_shutil:

            mock_temp.mkdtemp.return_value = '/home/test/'
            mock_pip.main.side_effect = Exception('Boom!')

            with pytest.raises(Exception):
                build_dependent_packages({'test': 'test'})

            mock_shutil.rmtree.assert_called_once_with(mock_temp.mkdtemp.return_value)


def test_fpm_command_dependencies_and_extra_args():
    with patch('vdt.versionplugin.buildout.shared.os.path') as mock_os_path:
        mock_os_path.join.return_value = 'files/preremove'
        fpm_ret = fpm_command('test', './home/test/setup.py',
                              no_python_dependencies=True,
                              extra_args=['-d', 'test'])
        assert fpm_ret == ['fpm', '-s', 'python', '-t', 'deb', '--maintainer=CSI',
                           '--exclude=*.pyc', '--exclude=*.pyo', '--depends=python',
                           '--category=python', '--template-scripts',
                           '--python-install-lib=/usr/lib/python2.7/dist-packages/',
                           '--python-install-bin=/usr/local/bin/',
                           '--before-remove=files/preremove', '--no-python-dependencies',
                           '-d', 'test', './home/test/setup.py']


def test_fpm_command_dependencies_and_no_extra_args():
    with patch('vdt.versionplugin.buildout.shared.os.path') as mock_os_path:
        mock_os_path.join.return_value = 'files/preremove'
        fpm_ret = fpm_command('test', './home/test/setup.py',
                              no_python_dependencies=True)
        assert fpm_ret == ['fpm', '-s', 'python', '-t', 'deb', '--maintainer=CSI',
                           '--exclude=*.pyc', '--exclude=*.pyo', '--depends=python',
                           '--category=python', '--template-scripts',
                           '--python-install-lib=/usr/lib/python2.7/dist-packages/',
                           '--python-install-bin=/usr/local/bin/',
                           '--before-remove=files/preremove', '--no-python-dependencies',
                           './home/test/setup.py']


def test_fpm_command_no_dependencies_and_no_extra_args():
    with patch('vdt.versionplugin.buildout.shared.os.path') as mock_os_path:
        mock_os_path.join.return_value = 'files/preremove'
        fpm_ret = fpm_command('test', './home/test/setup.py')
        assert fpm_ret == ['fpm', '-s', 'python', '-t', 'deb', '--maintainer=CSI',
                           '--exclude=*.pyc', '--exclude=*.pyo', '--depends=python',
                           '--category=python', '--template-scripts',
                           '--python-install-lib=/usr/lib/python2.7/dist-packages/',
                           '--python-install-bin=/usr/local/bin/',
                           '--before-remove=files/preremove', './home/test/setup.py']


def test_fpm_command_broken_scheme():
    with patch('vdt.versionplugin.buildout.shared.os.path') as mock_os_path:
        mock_os_path.join.return_value = 'files/preremove'
        fpm_ret = fpm_command('pyyaml', './home/test/setup.py')
        assert fpm_ret == ['fpm', '-n', 'python-yaml', '-s', 'python', '-t', 'deb',
                           '--maintainer=CSI', '--exclude=*.pyc', '--exclude=*.pyo',
                           '--depends=python', '--category=python', '--template-scripts',
                           '--python-install-lib=/usr/lib/python2.7/dist-packages/',
                           '--python-install-bin=/usr/local/bin/',
                           '--before-remove=files/preremove', './home/test/setup.py']


def test_fpm_command_version():
    with patch('vdt.versionplugin.buildout.shared.os.path') as mock_os_path:
        mock_os_path.join.return_value = 'files/preremove'
        expected_result = ['fpm', '-n', 'python-yaml', '-s', 'python', '-t', 'deb',
                           '--version=1.2.0-jenkins-704', '--maintainer=CSI', '--exclude=*.pyc',
                           '--exclude=*.pyo', '--depends=python', '--category=python',
                           '--template-scripts',
                           '--python-install-lib=/usr/lib/python2.7/dist-packages/',
                           '--python-install-bin=/usr/local/bin/',
                           '--before-remove=files/preremove', './home/test/setup.py']
        result = fpm_command('pyyaml', './home/test/setup.py', version='1.2.0-jenkins-704')
        assert sorted(result) == sorted(expected_result)


def test_read_dependencies():
    with patch('vdt.versionplugin.buildout.shared.log'):
            file_name = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files/setup.py')
            expected_result = sorted(['setuptools', 'pyyaml', 'puka', 'couchbase'])
            result = sorted(read_dependencies(file_name))
            assert result == expected_result


def test_extend_extra_args_with_versions():
    with patch('vdt.versionplugin.buildout.shared.log'):
        extra_args = ['--test-1', '--test-2']
        dependencies_with_versions = {'setuptools': '1.0.0', 'puka': '2.0.0'}
        expected_result = sorted(['--test-1', '--test-2',
                                  '-d', 'python-setuptools = 1.0.0',
                                  '-d', 'python-puka = 2.0.0'])
        result = sorted(extend_extra_args(extra_args, dependencies_with_versions))

        assert result == expected_result


def test_extend_extra_args_without_versions():
    with patch('vdt.versionplugin.buildout.shared.log'):
        extra_args = ['--test-1', '--test-2']
        dependencies_with_versions = {'setuptools': None, 'puka': None}
        expected_result = sorted(['--test-1', '--test-2',
                                  '-d', 'python-setuptools',
                                  '-d', 'python-puka'])
        result = sorted(extend_extra_args(extra_args, dependencies_with_versions))

        assert result == expected_result


def test_extend_extra_args_broken_scheme():
    with patch('vdt.versionplugin.buildout.shared.log'):
        extra_args = ['--test-1', '--test-2']
        dependencies_with_versions = {'pyyaml': None, 'pyzmq': '1.0.0'}
        expected_result = sorted(['--test-1', '--test-2',
                                  '-d', 'python-yaml',
                                  '-d', 'python-zmq = 1.0.0'])
        result = sorted(extend_extra_args(extra_args, dependencies_with_versions))

        assert result == expected_result


def _side_effect_get(_, dependency):
    if dependency == 'pyyaml':
        return '1.0.0'
    elif dependency == 'puka':
        return '2.0.0'
    elif dependency == 'setuptools':
        return '3.0.0'


def _side_effect_has_option(_, dependency):
    if dependency == 'pyyaml':
        return True
    elif dependency == 'puka':
        return True
    elif dependency == 'setuptools':
        return True


def test_lookup_versions():
    with patch('vdt.versionplugin.buildout.shared.log'),\
            patch('vdt.versionplugin.buildout.shared.ConfigParser.ConfigParser.has_option',
                  Mock(side_effect=_side_effect_has_option), create=True),\
            patch('vdt.versionplugin.buildout.shared.ConfigParser.ConfigParser.get',
                  Mock(side_effect=_side_effect_get), create=True):

            expected_result = {'pyyaml': '1.0.0', 'puka': '2.0.0',
                               'setuptools': '3.0.0', 'pyzmq': None}
            result = lookup_versions(['pyyaml', 'puka', 'setuptools', 'pyzmq'], 'versions.cfg')
            assert result == expected_result


def test_parse_version_extra_args():
    args, extra_args = parse_version_extra_args(['--include', 'test1', '-i', 'test2',
                                                 '--versions-file', '/home/test/versions.cfg',
                                                 '-d', '--test1', '-d', '--test2'])
    assert sorted(args.include) == sorted(['test1', 'test2'])
    assert args.versions_file == '/home/test/versions.cfg'
    assert sorted(extra_args) == sorted(['-d', '--test1', '-d', '--test2'])