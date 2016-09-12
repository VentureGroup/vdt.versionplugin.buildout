from mock import call, Mock
import pytest

from vdt.versionplugin.buildout.shared import delete_old_packages


@pytest.fixture
def mock_logger(monkeypatch):
    monkeypatch.setattr('vdt.versionplugin.buildout.shared.log', Mock())


def test_delete_old_packages(monkeypatch, mock_logger):
    monkeypatch.setattr('vdt.versionplugin.buildout.shared.glob.glob',
                        Mock(return_value=['test-1.deb', 'test-2.deb', 'test-3.deb']))
    mock_os = Mock()
    monkeypatch.setattr('vdt.versionplugin.buildout.shared.os.remove', mock_os)

    delete_old_packages()

    mock_os.assert_has_calls([call('test-1.deb'), call('test-2.deb'), call('test-3.deb')])