from __future__ import annotations

import argparse
import os
import shlex
import socket
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from os import linesep
from pathlib import Path
from typing import Any, cast

import regex
from lxml import etree
from lxml.etree import _ElementTree

from tests.integration_tests.download_cache import download_and_apply_cache


def assert_result(errors: list[str]) -> None:
    assert len(errors) == 0, f"Errors encountered during test:\n{linesep.join(errors)}"


def parse_args(
    name: str,
    description: str,
    arelle: bool = True,
    cache: str | None = None,
    cache_version_id: str | None = None,
    working_directory: bool = True,
) -> argparse.Namespace:
    """
    Parses standard integration test script arguments and returns the results
    after some preprocessing based on values.
    :param name: Name of the test. Note that this is used in the default working directory path.
    :param description: Human-readable description of the test.
    :param arelle: Whether '--arelle' argument is required.
    :param cache: Name of the cache that will be downloaded if `--download-cache` is provided.
    :param cache_version_id: Version of the cache that will be downloaded if `--download-cache` is provided.
    :param working_directory: Whether a working directory should be configured.
    :return: Parsed argument Namespace.
    """
    parser = argparse.ArgumentParser(prog=name, description=description)
    parser.add_argument("--arelle", action="store", required=arelle,
                        help="CLI command to run Arelle.")
    parser.add_argument("--download-cache", action="store_true",
                        help="Whether or not to download and apply cache.")
    parser.add_argument("--offline", action="store_true",
                        help="True if Arelle should run in offline mode.")
    parser.add_argument("--working-directory", action="store", default=".test",
                        help="Directory to place temporary files and log output.")
    parsed_args = parser.parse_args()
    if cache and parsed_args.download_cache:
        download_and_apply_cache(f"scripts/{cache}", version_id=cache_version_id)
        print(f"Downloaded and applied cache: {cache}")
    if working_directory:
        test_directory = Path(parsed_args.working_directory).joinpath(name).absolute()
        parsed_args.test_directory = test_directory
        test_directory.mkdir(parents=True, exist_ok=True)
        print(f"Set test directory: {test_directory}")
    return parsed_args


def prepare_logfile(working_directory: Path, script_path: Path, name: str | None = None, ext: str = "xml") -> Path:
    name_part = "" if name is None else f".{name}"
    logfile_path = working_directory.joinpath(script_path.stem).with_suffix(f"{name_part}.logfile.{ext}")
    logfile_path.unlink(missing_ok=True)
    return logfile_path


def _get_arelle_args(
    arelle_command: str,
    plugins: list[str] | None = None,
    additional_args: list[str] | None = None,
    offline: bool = False,
    logFile: Path | None = None,
    logFormat: str = "[%(messageCode)s] %(message)s - %(file)s",
) -> list[str]:
    if os.name == "nt":
        args = [sys.executable if w == "python" else w for w in arelle_command.split()]
    else:
        args = shlex.split(arelle_command)
    if plugins:
        args.append(f"--plugins={'|'.join(plugins)}")
    if offline:
        args.append("--internetConnectivity=offline")
    args.extend(additional_args or [])
    if logFile:
        args.extend(["--logFile", str(logFile)])
        args.extend(["--logFormat", logFormat])
    return args


def run_arelle_cmd(
    arelle_command: str,
    plugins: list[str] | None = None,
    additional_args: list[str] | None = None,
    offline: bool = False,
    logFile: Path | None = None,
    logFormat: str = "[%(messageCode)s] %(message)s - %(file)s",
) -> subprocess.CompletedProcess[bytes]:
    """
    Executes an Arelle command using subprocess and returns the completed process.

    The function constructs the command-line arguments needed to execute an Arelle
    command by combining the provided parameters.

    :param arelle_command: The base Arelle command that needs to be executed.
    :param plugins: A list of plugins to enable during the execution. Defaults to None.
    :param additional_args: Additional arguments to include when executing the command. Defaults to None.
    :param offline: A boolean flag indicating whether the command should be executed in offline
        mode. Defaults to False.
    :param logFile: The file path for logging the output of the Arelle command. Defaults to None.
    :param logFormat: The format of the log messages. Defaults to "[%(messageCode)s] %(message)s - %(file)s".

    :return: Returns a CompletedProcess instance containing information about the executed process,
        including its output, return code, and other attributes.
    """
    args = _get_arelle_args(
        arelle_command,
        plugins,
        additional_args,
        offline,
        logFile,
        logFormat,
    )
    return subprocess.run(args, capture_output=True)

def run_arelle(
    arelle_command: str,
    plugins: list[str] | None = None,
    additional_args: list[str] | None = None,
    offline: bool = False,
    logFile: Path | None = None,
    logFormat: str = "[%(messageCode)s] %(message)s - %(file)s",
) -> None:
    result = run_arelle_cmd(
        arelle_command,
        plugins,
        additional_args,
        offline,
        logFile,
        logFormat,
        )
    assert result.returncode == 0, result.stderr.decode().strip()


def _probe_error_kind(exc: OSError) -> str:
    if isinstance(exc, ConnectionRefusedError):
        return "refused"
    if isinstance(exc, TimeoutError):
        return "connect-timeout"
    return f"{type(exc).__name__}:{getattr(exc, 'errno', None)}"


def _diagnose_unready_webserver(
    port: int,
    proc: subprocess.Popen[bytes],
) -> str:
    lines = [f"webserver pid={proc.pid} poll={proc.poll()} port={port}"]
    if sys.platform != "darwin":
        return "\n".join(lines)
    for args in (
        ["lsof", "-nP", f"-iTCP:{port}"],
        ["sample", str(proc.pid), "3"],
    ):
        lines.append(f"$ {' '.join(args)}")
        try:
            result = subprocess.run(
                args, capture_output=True, timeout=30, check=False
            )
        except OSError as exc:
            lines.append(str(exc))
            continue
        output = (result.stdout or result.stderr).decode(
            errors="replace"
        ).strip()
        lines.append(output or f"(exit {result.returncode}, no output)")
    return "\n".join(lines)


def wait_for_localhost_port(
    port: int,
    proc: subprocess.Popen[bytes],
    timeout: float = 180,
) -> None:
    """
    Block until 127.0.0.1 accepts a TCP connection on *port*.
    """
    counts: dict[str, int] = defaultdict(int)
    started = time.monotonic()
    deadline = started + timeout
    last_heartbeat = -1
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Arelle webserver exited with code {proc.returncode} "
                f"before listening on port {port}. probe_counts={dict(counts)}"
            )
        elapsed = time.monotonic() - started
        heartbeat = int(elapsed) // 10
        if heartbeat != last_heartbeat:
            last_heartbeat = heartbeat
            print(
                f"webserver probe t={elapsed:.1f}s counts={dict(counts)}",
                file=sys.stderr,
                flush=True,
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                print(
                    f"webserver probe connected after {elapsed:.2f}s "
                    f"counts={dict(counts)}",
                    file=sys.stderr,
                    flush=True,
                )
                return
        except OSError as exc:
            last_error = exc
            counts[_probe_error_kind(exc)] += 1
            time.sleep(0.1)
    diagnosis = _diagnose_unready_webserver(port, proc)
    print(diagnosis, file=sys.stderr, flush=True)
    raise TimeoutError(
        f"Arelle webserver did not accept connections on port {port} "
        f"within {timeout} seconds. probe_counts={dict(counts)} "
        f"last_error={last_error!r}\n{diagnosis}"
    )


@contextmanager
def run_arelle_webserver(
    arelle_command: str,
    port: int = 8080,
    plugins: list[str] | None = None,
    additional_args: list[str] | None = None,
    offline: bool = False,
) -> Generator[subprocess.Popen[bytes]]:
    additional_args = ["--webserver", f"localhost:{port}"] + (additional_args or [])
    args = _get_arelle_args(arelle_command, plugins, additional_args, offline)
    proc = None
    try:
        print(f"Starting web server on port {port}...")
        proc = subprocess.Popen(args)
        print(f"Waiting for web server on port {port}...")
        wait_for_localhost_port(port, proc)
        print("Web server ready.")
        yield proc
    finally:
        print("Exiting web server...")
        if proc:
            proc.kill()
        print("Web server exited.")


def validate_log_file(
    logfile_path: Path,
    expected_results: dict[str, dict[regex.Pattern[str], int]] | None = None,
) -> list[str]:
    if not logfile_path.exists():
        return [f'Log file "{logfile_path}" not found.']
    tree = etree.parse(logfile_path)
    return validate_log_tree(tree, expected_results)


def validate_log_text(
        logfile_path: Path,
        expected_results: dict[regex.Pattern[str], int] | None = None,
) -> list[str]:
    if not logfile_path.exists():
        return [f'Log file "{logfile_path}" not found.']
    expected_results = expected_results or {}
    results = []
    with open(logfile_path) as f:
        logs = f.read()
    for pattern, expected_count in expected_results.items():
        matches = regex.findall(pattern, logs)
        actual_count = len(matches)
        if actual_count != expected_count:
            results.append(f'Expected {expected_count} occurrence(s) of "{pattern.pattern}" but found {actual_count}.')
    return results


def validate_log_tree(
        tree: _ElementTree,
        expected_results: dict[str, dict[regex.Pattern[str], int]] | None = None,
) -> list[str]:
    expected_results = expected_results or {}
    if "error" not in expected_results:
        expected_results["error"] = {}
    level_messages = {}
    for level in expected_results:
        level_messages[level] = cast(Iterable[Any], tree.xpath(f"//log/entry[@level='{level}']/message/text()"))
    results = []
    actual_results: dict[str, dict[regex.Pattern[str], int]] = defaultdict(lambda: defaultdict(int))
    for level, messages in level_messages.items():
        for message in messages:
            any_match = False
            for pattern, expected_count in expected_results[level].items():
                if pattern.match(message):
                    any_match = True
                    actual_results[level][pattern] += 1
            if not any_match and level == "error":
                results.append(message)
        for pattern, expected_count in expected_results[level].items():
            actual_count = actual_results[level][pattern]
            if actual_count != expected_count:
                results.append(f'Expected {expected_count} occurrence(s) of {level} "{pattern.pattern}" but found {actual_count}.')
    return results


def validate_log_xml(
        xml: str | bytes,
        expected_results: dict[str, dict[regex.Pattern[str], int]] | None = None,
) -> list[str]:
    tree = etree.fromstring(xml)
    return validate_log_tree(tree.getroottree(), expected_results)
