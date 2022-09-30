from datetime import datetime
import mock

import arelle.Version
from arelle.Version import getVersion, getGitHash, getDefaultVersion

expected_copyright_year = datetime.now().year


def test_version_dot_py_exists():
    expected_version = '9.2.2.dev1128+g85b8787b.d20220928'

    with mock.patch('arelle.Version.getBuildVersion') as build_version:
        build_version.return_value = expected_version
        assert getVersion() == arelle.Version.getBuildVersion() == expected_version


def test_git_rev_parse_head_fallback():
    _git_rev_parse_head = '85b8787b1bcfcb236fd76b7d6dfc8ecda59c663b\n'
    expected_version = _git_rev_parse_head.strip()

    with mock.patch('arelle.Version.getBuildVersion') as build_version:
        build_version.return_value = None
        #  Mock 'git rev-parse HEAD' result
        with mock.patch("subprocess.run") as mock_subproc_run:
            process_mock = mock.Mock(
                stdout=_git_rev_parse_head,
                stderr=''
            )
            mock_subproc_run.return_value = process_mock
            assert getVersion() == getGitHash() == expected_version


def test_git_not_installed_fallback():
    expected_version = '0.0.0'

    with mock.patch('arelle.Version.getBuildVersion') as build_version:
        build_version.return_value = None
        #  Mock 'git rev-parse HEAD' result
        with mock.patch("subprocess.run") as mock_subproc_run:
            process_mock = mock.Mock(
                stdout='',
                stderr="FileNotFoundError: [Errno 2] No such file or directory: 'git'"
            )
            mock_subproc_run.return_value = process_mock
            assert getVersion() == getDefaultVersion() == expected_version
