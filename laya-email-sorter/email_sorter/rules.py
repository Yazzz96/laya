"""Cheap header signals, checked before the model runs."""
import re
from typing import Dict, List

_NOREPLY = re.compile(r"(no-?reply|do-?not-?reply|donotreply|notifications?|mailer|newsletter|news|marketing|promo)@",
                      re.I)
_GMAIL_BULK = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS"}


def header_signals(headers: Dict[str, str], labels: List[str]) -> Dict[str, bool]:
    """Return boolean signals from raw headers and Gmail label ids."""
    h = {k.lower(): v or "" for k, v in headers.items()}
    sender = h.get("from", "")
    labels = set(labels or [])
    return {
        "bulk": bool(h.get("list-unsubscribe") or h.get("list-id")
                     or h.get("precedence", "").lower() in ("bulk", "list", "junk")),
        "noreply": bool(_NOREPLY.search(sender)),
        "gmail_bulk_category": bool(labels & _GMAIL_BULK),
        "starred": "STARRED" in labels,
        "gmail_important": "IMPORTANT" in labels,
        "unread": "UNREAD" in labels,
    }
