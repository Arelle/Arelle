"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import atexit
import os
import zipfile
from optparse import OptionParser
from pathlib import Path, PurePath
from typing import Any, Literal, cast

from arelle.Cntlr import Cntlr
from arelle.RuntimeOptions import RuntimeOptions
from arelle.Version import authorLabel, copyrightLabel
from arelle.utils.PluginHooks import PluginHooks

PLUGIN_NAME = "Cache Builder"


class CacheBuilder:
    cacheDirectory: str
    cacheZip: zipfile.ZipFile
    existingPaths: frozenset[str]
    visitedPaths: set[str]

    def __init__(self, cntlr: Cntlr, cacheZip: zipfile.ZipFile):
        self.cacheDirectory = cntlr.webCache.cacheDir
        self.cacheZip = cacheZip
        self.existingPaths = frozenset(cacheZip.namelist())
        self.visitedPaths = set()

    def copyFileToCache(self, filepath: str):
        """
        Copies the file at `filepath` to its corresponding location in the output archive if:
        - `filepath` has not already been seen by the plugin during this run.
        - `filepath` is a path within `cacheDirectory`
        - The destination path corresponding to `filepath` does not already exist in the archive.
        An error will be raised if a source file to be copied does not exist.

        :param filepath: Full filepath of file to copy.
        """
        # If filepath is among source filepaths already visited during this run, skip it.
        if filepath in self.visitedPaths:
            return
        self.visitedPaths.add(filepath)
        # If filepath is not within web cache, skip it.
        filePurePath = PurePath(filepath)
        if not filePurePath.is_relative_to(self.cacheDirectory):
            return
        # If the destination path is among the destination filepaths that already existed in the archive, skip it.
        destination = filePurePath.relative_to(self.cacheDirectory).as_posix()
        if destination in self.existingPaths:
            return
        # If the source file does not exist, skip it.
        if not Path(filepath).exists():
            raise IOError(_('Cache builder attempted to copy file that does not exist at "{0}".').format(filepath))
        self.cacheZip.write(filepath, destination)
        return


class CacheBuilderPlugin(PluginHooks):
    cacheBuilder: CacheBuilder | None = None

    @staticmethod
    def cntlrCmdLineOptions(
        parser: OptionParser,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        parser.add_option(
            '--cache-builder-path',
            action='store',
            dest='cacheBuilderPath',
            help='Sets the path where the cache builder output should be written to. If an archive does not exist it will be created.',
        )
        parser.add_option(
            '--cache-builder-append',
            action='store_true',
            dest='cacheBuilderAppend',
            help='Sets whether the cache builder should append to an existing archive or overwrite it.',
        )

    @staticmethod
    def cntlrCmdLineUtilityRun(cntlr: Cntlr, options: RuntimeOptions, *args: Any, **kwargs: Any) -> None:
        assert CacheBuilderPlugin.cacheBuilder is None, \
            'Cache builder attempted to create multiple cache archives in the same plugin lifecycle.'
        assert options.cacheBuilderPath is not None, \
            '"cacheBuilderPath" must be set for cache builder to run.'
        os.makedirs(Path(options.cacheBuilderPath).parent, exist_ok=True)
        mode = 'a' if options.cacheBuilderAppend else 'w'
        cacheZip = zipfile.ZipFile(options.cacheBuilderPath, cast(Literal, mode), zipfile.ZIP_DEFLATED)
        atexit.register(cacheZip.close)
        CacheBuilderPlugin.cacheBuilder = CacheBuilder(cntlr, cacheZip)

    @staticmethod
    def fileSourceFile(cntlr: Cntlr, filepath: str, *args: Any, **kwargs: Any) -> None:
        if CacheBuilderPlugin.cacheBuilder is not None:
            CacheBuilderPlugin.cacheBuilder.copyFileToCache(filepath)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "0.0.1",
    "description": "Generate cache archives from web documents referenced during an Arelle application lifecycle.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    'CntlrCmdLine.Options': CacheBuilderPlugin.cntlrCmdLineOptions,
    'CntlrCmdLine.Utility.Run': CacheBuilderPlugin.cntlrCmdLineUtilityRun,
    "FileSource.File": CacheBuilderPlugin.fileSourceFile,
}
