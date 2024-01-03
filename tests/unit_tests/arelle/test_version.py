import subprocess

from unittest import mock

import arelle.Version
from arelle.Version import getDefaultVersion, getGitHash, getVersion


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
            mock_subproc_run.side_effect = FileNotFoundError
            assert getVersion() == getDefaultVersion() == expected_version


def test_git_error():
    expected_version = '0.0.0'

    with mock.patch('arelle.Version.getBuildVersion') as build_version:
        build_version.return_value = None
        #  Mock 'git rev-parse HEAD' result
        with mock.patch("subprocess.run") as mock_subproc_run:
            mock_subproc_run.side_effect = subprocess.SubprocessError("fatal: not a git repository (or any of the parent directories): .git")
            assert getVersion() == getDefaultVersion() == expected_version
