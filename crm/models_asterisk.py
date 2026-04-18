"""Back-compat re-export shim.

The shadow Asterisk-realtime models used to be planned inside ``crm/``. They
now live in the dedicated ``asterisk_state`` app so Django's app_label /
migration scoping stays clean (see ``asterisk_state/models.py``).

This module re-exports them so other parts of the codebase can still do::

    from crm.models_asterisk import PsEndpoint, AsteriskQueue
"""
from asterisk_state.models import (  # noqa: F401
    AsteriskQueue,
    AsteriskQueueMember,
    PsAor,
    PsAuth,
    PsContact,
    PsEndpoint,
    PsIdentify,
    PsRegistration,
)

__all__ = [
    "PsEndpoint",
    "PsAuth",
    "PsAor",
    "PsIdentify",
    "PsContact",
    "PsRegistration",
    "AsteriskQueue",
    "AsteriskQueueMember",
]
