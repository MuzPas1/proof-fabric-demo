"""Cross-SDK parity regression — verifies shipped test vectors with the
Python SDK and (if node is available) the JavaScript SDK, for every suite."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SDKS = REPO / "sdks"
sys.path.insert(0, str(SDKS / "python"))

VECTORS = SDKS / "test_vectors.json"


def _load():
    if not VECTORS.exists():
        pytest.skip("test_vectors.json not generated")
    return json.loads(VECTORS.read_text())["fea"]


def test_python_sdk_verifies_all_suites():
    from pfp_sdk.verify import verify_fea
    vectors = _load()
    assert len(vectors) >= 1
    for v in vectors:
        res = verify_fea(v["fea_payload"], v["signature"], v["public_key_b64"])
        assert res["valid"] is True, f"{v['suite']}: {res}"


def test_python_sdk_rejects_tampered_all_suites():
    from pfp_sdk.verify import verify_fea
    for v in _load():
        tampered = json.loads(json.dumps(v["fea_payload"]))
        tampered["transaction_summary"]["amount"] = 999999999
        res = verify_fea(tampered, v["signature"], v["public_key_b64"])
        assert res["valid"] is False, f"{v['suite']} tamper not detected"


def test_python_sdk_wrong_suite_key_rejected():
    """A signature verified against another suite's key must fail."""
    from pfp_sdk.verify import verify_fea
    vectors = {v["suite"]: v for v in _load()}
    if "ES256" in vectors and "ES256K" in vectors:
        a, b = vectors["ES256"], vectors["ES256K"]
        # Verify ES256 payload/sig but with ES256K's key + algorithm → invalid.
        res = verify_fea(a["fea_payload"], a["signature"], b["public_key_b64"], algorithm="ES256K")
        assert res["valid"] is False


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_sdk_parity():
    script = SDKS / "javascript" / "parity_test.js"
    proc = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
