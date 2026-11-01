import base64

import pytest

from eil.supply_chain import validate_lock


def lock(**updates):
    package = {
        "version": "1.0.0",
        "resolved": "https://registry.npmjs.org/demo/-/demo-1.0.0.tgz",
        "integrity": "sha512-" + base64.b64encode(b"x" * 64).decode(),
        **updates,
    }
    return {"lockfileVersion": 3, "packages": {"": {}, "node_modules/demo": package}}


def test_registry_lock_accepts_pinned_packages_without_running_hooks():
    assert validate_lock(lock()) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"resolved": "git+https://external.invalid/demo.git"},
        {"resolved": "http://registry.npmjs.org/demo.tgz"},
        {"integrity": "sha512-not-a-digest"},
        {"link": True},
        {"hasInstallScript": True},
    ],
)
def test_new_registry_integrity_or_install_hook_risk_fails_closed(changes):
    assert validate_lock(lock(**changes))
