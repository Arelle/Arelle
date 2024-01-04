import pytest
import re

from unittest.mock import patch
from arelle.RuntimeOptions import RuntimeOptions, RuntimeOptionsException


def test_existing_plugin_options_collision():
    with pytest.raises(RuntimeOptionsException, match=re.escape("Provided plugin options already exist as base options ['uiLang']")):
        RuntimeOptions(
            entrypointFile='fr',
            pluginOptions={
                'uiLang': 'fr',
            },
        )


@patch('arelle.RuntimeOptions.hasWebServer')
def test_webserver_requires_module(mockwebserver):
    mockwebserver.return_value = False
    with pytest.raises(RuntimeOptionsException, match='Webserver option requires webserver module'):
        RuntimeOptions(
            webserver='webserver',
        )


def test_incorrect_arguments_with_webserver():
    with pytest.raises(RuntimeOptionsException, match='Incorrect arguments with webserver'):
        RuntimeOptions(
            entrypointFile='File',
            webserver='webserver',
        )


@patch('arelle.RuntimeOptions.hasWebServer')
def test_incorrect_arguments(mockwebserver):
    with pytest.raises(RuntimeOptionsException, match="Incorrect arguments"):
        mockwebserver.return_value = False
        RuntimeOptions(
            entrypointFile=None,
            proxy=None,
            plugins=None,
            pluginOptions=None,
            webserver=None,
        )


def test_set_runtime_options():
    runtimeOptions = RuntimeOptions(
        abortOnMajorError=True,
        pluginOptions={
            'dynamicNamedOptionDefinedByPlugin': 42,
        },
    )
    assert runtimeOptions.abortOnMajorError
    assert runtimeOptions.dynamicNamedOptionDefinedByPlugin == 42
