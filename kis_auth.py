"""Compatibility shim.

The upstream KIS sample code (under examples_user/) imports `kis_auth` from the
project root. In this repo, the maintained implementation lives in
`src/core/kis_auth.py`.

This shim re-exports the core implementation so examples/tools keep working.
"""

from __future__ import annotations

import os
import sys

# Ensure `stock/open-trading-api-v2/src` is on sys.path
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_THIS_DIR, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# Re-export everything from the core auth module (including underscore helpers
# that the sample functions rely on).
import core.kis_auth as _core_kis_auth

globals().update({k: getattr(_core_kis_auth, k) for k in dir(_core_kis_auth) if not k.startswith('__')})
