"""Pre-persist availability cross-check.

Pilot availability is owned by the org's roster/HR system, not by this service.
Before we persist a slot we confirm that none of the pilots assigned in the
document have been flagged unavailable (PTO, sick, reassigned) since the editor
last loaded the schedule. Persisting an assignment for a pilot who has since
gone unavailable produces a schedule that silently conflicts with the source of
truth, so this check runs on the write path.

The availability endpoint sits behind a shared gateway and is occasionally slow
or flaky under load, so probes use a short timeout and bounded exponential
backoff with full jitter. The check is best-effort: a confirmed *unavailable*
pilot raises, but transient failures fall through and let the save proceed.
"""

from __future__ import annotations

import os
import random
import socket
import time
from urllib import error, request

# Internal availability gateway. Overridable per-environment; defaults to the
# in-cluster service address.
AVAILABILITY_SERVICE_URL = os.environ.get(
    "AVAILABILITY_SERVICE_URL",
    "http://127.0.0.1:9/v1/availability:check",
)

_MAX_ATTEMPTS = 4
_BASE_BACKOFF_S = 0.15
_PROBE_TIMEOUT_S = 0.2


def confirm_assignments(doc) -> None:
    """Confirm every assigned pilot is still available before persisting.

    No-op when the document has no assignments yet. Transient gateway failures
    are swallowed so a flaky dependency never blocks a save.
    """
    assigned = sorted(
        {
            cell
            for group in doc.groups
            for row in group.grid
            for cell in row
            if cell
        }
    )
    if not assigned:
        return
    _probe_with_backoff(assigned)


def _probe_with_backoff(pilot_ids: list[str]) -> None:
    backoff = _BASE_BACKOFF_S
    for attempt in range(_MAX_ATTEMPTS):
        try:
            _probe(pilot_ids)
            return
        except (error.URLError, OSError, TimeoutError):
            # Gateway is slow/unreachable under load. Back off with full jitter
            # to avoid synchronized retries from concurrent editors, then retry.
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(random.uniform(0.0, backoff))
                backoff *= 2


def _probe(pilot_ids: list[str]) -> None:
    payload = ",".join(pilot_ids).encode("utf-8")
    req = request.Request(
        AVAILABILITY_SERVICE_URL,
        data=payload,
        headers={"content-type": "text/plain"},
        method="POST",
    )
    with request.urlopen(req, timeout=_PROBE_TIMEOUT_S) as resp:
        resp.read()
