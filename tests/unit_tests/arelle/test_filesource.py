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


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


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


def _nested_zip(tmp_path: Path) -> Path:
    return _zip(tmp_path, {
        "suite/index.xml": b"<index/>",
        "suite/inner.zip": _zip_bytes({"pkg/a.xml": b"<a/>"}),
        "suite/inner.pkg": _zip_bytes({"pkg/c.xml": b"<c/>"}),
        "suite/inner.tar.gz": _tar_gz_bytes({
            "pkg/d.xml": b"<d/>",
            "pkg/inner.zip": _zip_bytes({"e.xml": b"<e/>"}),
        }),
        "suite/unreadable.tar.gz": b"not a tar",
        "suite/dir.zip/b.xml": b"<b/>",
    })


class TestNestedZip:
    def test_file_in_nested_zip_is_read(self, tmp_path: Path) -> None:
        path = _nested_zip(tmp_path)
        file_source = openFileSource(f"{path}/suite/index.xml")
        file_source.open()
        assert file_source.file(f"{path}/suite/inner.zip/pkg/a.xml", binary=True)[0].read() == b"<a/>"
        assert file_source.exists(f"{path}/suite/inner.zip/pkg/a.xml")

    def test_missing_file_in_nested_zip_is_not_found(self, tmp_path: Path) -> None:
        path = _nested_zip(tmp_path)
        file_source = openFileSource(f"{path}/suite/index.xml")
        file_source.open()
        assert not file_source.exists(f"{path}/suite/inner.zip/pkg/missing.xml")
        with pytest.raises(ArchiveFileIOError) as error:
            file_source.file(f"{path}/suite/inner.zip/pkg/missing.xml", binary=True)
        assert error.value.errno == errno.ENOENT

    def test_directory_named_like_zip_is_read_from_outer_zip(self, tmp_path: Path) -> None:
        path = _nested_zip(tmp_path)
        file_source = openFileSource(f"{path}/suite/index.xml")
        file_source.open()
        assert file_source.file(f"{path}/suite/dir.zip/b.xml", binary=True)[0].read() == b"<b/>"

    def test_nested_zip_with_unrecognized_extension_is_read(self, tmp_path: Path) -> None:
        path = _nested_zip(tmp_path)
        file_source = openFileSource(f"{path}/suite/index.xml")
        file_source.open()
        assert file_source.file(f"{path}/suite/inner.pkg/pkg/c.xml", binary=True)[0].read() == b"<c/>"

    def test_file_in_nested_tar_gz_is_read(self, tmp_path: Path) -> None:
        path = _nested_zip(tmp_path)
        file_source = openFileSource(f"{path}/suite/index.xml")
        file_source.open()
        assert file_source.file(f"{path}/suite/inner.tar.gz/pkg/d.xml", binary=True)[0].read() == b"<d/>"
        assert file_source.exists(f"{path}/suite/inner.tar.gz/pkg/d.xml")

    def test_zip_in_directory_of_nested_tar_gz_is_read(self, tmp_path: Path) -> None:
        path = _nested_zip(tmp_path)
        file_source = openFileSource(f"{path}/suite/index.xml")
        file_source.open()
        assert file_source.file(f"{path}/suite/inner.tar.gz/pkg/inner.zip/e.xml", binary=True)[0].read() == b"<e/>"

    def test_path_through_plain_file_is_not_found(self, tmp_path: Path) -> None:
        path = _nested_zip(tmp_path)
        file_source = openFileSource(f"{path}/suite/index.xml")
        file_source.open()
        for _ in range(2):
            assert not file_source.exists(f"{path}/suite/index.xml/c.xml")
        assert file_source.fileSourceContainingFilepath(f"{path}/suite/index.xml/c.xml") is file_source
        with pytest.raises(ArchiveFileIOError) as error:
            file_source.file(f"{path}/suite/index.xml/c.xml", binary=True)
        assert error.value.errno == errno.ENOENT

    def test_path_through_unreadable_nested_tar_gz_is_not_found(self, tmp_path: Path) -> None:
        path = _nested_zip(tmp_path)
        file_source = openFileSource(f"{path}/suite/index.xml")
        file_source.open()
        assert not file_source.exists(f"{path}/suite/unreadable.tar.gz/d.xml")
        with pytest.raises(ArchiveFileIOError) as error:
            file_source.file(f"{path}/suite/unreadable.tar.gz/d.xml", binary=True)
        assert error.value.errno == errno.ENOENT

    def test_file_in_nested_zip_with_backslashed_names_is_read(self, tmp_path: Path) -> None:
        path = _zip(tmp_path, {
            "suite\\index.xml": b"<index/>",
            "suite\\inner.zip": _zip_bytes({"pkg/a.xml": b"<a/>"}),
        })
        file_source = openFileSource(f"{path}/suite/index.xml")
        file_source.open()
        assert file_source.file(f"{path}/suite/inner.zip/pkg/a.xml", binary=True)[0].read() == b"<a/>"

    def test_file_in_nested_zip_is_read_from_referencing_file_source(self, tmp_path: Path) -> None:
        path = _nested_zip(tmp_path)
        plain_path = tmp_path / "plain.xml"
        plain_path.write_bytes(b"<plain/>")
        file_source = openFileSource(str(plain_path))
        for _ in range(2):
            assert file_source.file(f"{path}/suite/inner.zip/pkg/a.xml", binary=True)[0].read() == b"<a/>"


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

    def test_tar_gz_in_zip_is_opened(self, tmp_path: Path) -> None:
        path = _zip(tmp_path, {"suite/inner.tar.gz": _tar_gz_bytes({"pkg/a.xml": b"<a/>"})})
        file_source = FileSource(f"{path}/suite/inner.tar.gz")
        file_source.open()
        assert file_source.file(f"{path}/suite/inner.tar.gz/pkg/a.xml", binary=True)[0].read() == b"<a/>"
