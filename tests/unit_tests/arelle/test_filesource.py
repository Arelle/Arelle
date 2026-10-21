from __future__ import annotations

import errno
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from arelle.FileSource import ArchiveFileIOError, FileSource, openFileSource


def _zip(tmp_path: Path, members: dict[str, bytes]) -> Path:
    path = tmp_path / "pkg.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def _tar_gz_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        directory = tarfile.TarInfo("pkg")
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


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


class TestTarGz:
    def test_unreadable_tar_gz_is_not_opened(self, tmp_path: Path) -> None:
        path = tmp_path / "pkg.tar.gz"
        path.write_bytes(b"not a tar")
        file_source = FileSource(str(path))
        file_source.open()
        assert not file_source.isOpen

    def test_missing_tar_gz_member_is_not_found(self, tmp_path: Path) -> None:
        path = tmp_path / "pkg.tar.gz"
        path.write_bytes(_tar_gz_bytes({"pkg/a.xml": b"<a/>"}))
        file_source = FileSource(str(path))
        file_source.open()
        assert file_source.file(f"{path}/pkg/a.xml", binary=True)[0].read() == b"<a/>"
        with pytest.raises(ArchiveFileIOError) as error:
            file_source.file(f"{path}/pkg/missing.xml", binary=True)
        assert error.value.errno == errno.ENOENT
