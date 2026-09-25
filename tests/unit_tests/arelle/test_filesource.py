from __future__ import annotations

import errno
import zipfile
from pathlib import Path

import pytest

from arelle.FileSource import ArchiveFileIOError, openFileSource


def _zip(tmp_path: Path, members: dict[str, bytes]) -> Path:
    path = tmp_path / "pkg.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


class TestStream:
    def test_zip_member_is_decompressed_as_it_is_read(self, tmp_path: Path) -> None:
        path = _zip(tmp_path, {"pkg/t.csv": b"a,b\n1,2\n"})
        file_source = openFileSource(f"{path}/pkg/t.csv")
        file_source.open()
        with file_source.stream(f"{path}/pkg/t.csv") as stream:
            assert isinstance(stream, zipfile.ZipExtFile)
            assert stream.read() == b"a,b\n1,2\n"

    def test_missing_zip_member_is_not_found(self, tmp_path: Path) -> None:
        path = _zip(tmp_path, {"pkg/t.csv": b""})
        file_source = openFileSource(f"{path}/pkg/t.csv")
        file_source.open()
        with pytest.raises(ArchiveFileIOError) as error:
            file_source.stream(f"{path}/pkg/missing.csv")
        assert error.value.errno == errno.ENOENT

    def test_plain_file_is_opened_from_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "t.csv"
        path.write_bytes(b"a,b\n1,2\n")
        file_source = openFileSource(str(path))
        with file_source.stream(str(path)) as stream:
            assert stream.read() == b"a,b\n1,2\n"
