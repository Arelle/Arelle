from __future__ import annotations

import urllib.parse
from pathlib import Path

import requests

from tests.integration_tests.scripts.script_util import (
    assert_result,
    parse_args,
    run_arelle_webserver,
)

errors: list[str] = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm the webserver rejects remote URL plug-in references.",
    arelle=False,
)
arelle_command = args.arelle

REJECTION_MESSAGE = "Remote URL plug-in references are not permitted via the webserver"

REMOTE_REJECT_CASES = [
    ("plain http", "plugins=http://example.invalid/evil.py"),
    ("https", "plugins=https://example.invalid/evil.py"),
    ("+ prefix", f"plugins={urllib.parse.quote_plus('+https://example.invalid/evil.py')}"),
    ("- prefix", f"plugins={urllib.parse.quote_plus('-http://example.invalid/evil.py')}"),
    ("~ prefix", f"plugins={urllib.parse.quote_plus('~http://example.invalid/evil.py')}"),
    ("pipe component", f"plugins={urllib.parse.quote_plus('validate/ESEF|http://example.invalid/evil.py')}"),
]

port = 8101
with run_arelle_webserver(arelle_command, port) as proc:
    base = f"http://localhost:{port}"

    for label, query in REMOTE_REJECT_CASES:
        url = f"{base}/rest/configure?{query}"
        print(f"Checking /rest/configure rejects: {label}")
        response = requests.get(url)
        if response.status_code != 400:
            errors.append(f"/rest/configure [{label}]: expected 400, got {response.status_code}; body: {response.text}")
        elif REJECTION_MESSAGE not in response.text:
            errors.append(
                f"/rest/configure [{label}]: 400 received but rejection message missing; body: {response.text}"
            )

    validation_url = f"{base}/rest/xbrl/validation?file=missing.xbrl&plugins=http://example.invalid/evil.py&media=text"
    print("Checking /rest/xbrl/validation rejects remote plug-in URL")
    response = requests.get(validation_url)
    if response.status_code != 400:
        errors.append(f"/rest/xbrl/validation: expected 400, got {response.status_code}; body: {response.text}")
    elif REJECTION_MESSAGE not in response.text:
        errors.append(f"/rest/xbrl/validation: 400 received but rejection message missing; body: {response.text}")

    sanity_url = f"{base}/rest/configure?plugins=validate/ESEF"
    print("Sanity check: local plug-in reference is still accepted")
    response = requests.get(sanity_url)
    if response.status_code == 400 and REJECTION_MESSAGE in response.text:
        errors.append(f"Local plug-in reference was incorrectly rejected; body: {response.text}")

    env_response = requests.get(f"{base}/rest/configure?environment")
    if "example.invalid" in env_response.text:
        errors.append(
            f"Environment response references example.invalid; a rejected plug-in may have been loaded: {env_response.text}"
        )

assert_result(errors)
