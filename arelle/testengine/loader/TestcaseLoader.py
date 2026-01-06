"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from arelle.testengine.TestEngineOptions import TestEngineOptions
from arelle.testengine.TestcaseVariationSet import TestcaseVariationSet

TESTCASE_LOADER_ERROR_PREFIX = "TESTCASE_LOADER"

class TestcaseLoader(ABC):

    @abstractmethod
    def is_loadable(self, test_engine_options: TestEngineOptions) -> bool:
        """
        Is the given index file able to be loaded by this loader?
        :param test_engine_options:
        :return:
        """
        pass

    @abstractmethod
    def load(self, test_engine_options: TestEngineOptions) -> TestcaseVariationSet:
        """
        Returns a testcase variation set generated based on the provided options.
        :param test_engine_options:
        :return:
        """
        pass
