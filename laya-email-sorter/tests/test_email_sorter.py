"""email_sorter decisions, with a fake router so no checkpoint or torch is needed."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_sorter import EmailSorter  # noqa: E402
from email_sorter.gmail_client import parse_message  # noqa: E402
from email_sorter.rules import header_signals  # noqa: E402


def ans(bucket, importance, action=0.1, phishing=0.02, conf=0.9):
    return {"answers": {
        "bucket": {"choice": bucket, "answer_confidence": conf},
        "importance": {"score": importance},
        "needs_action": {"noul": action},
        "is_phishing": {"noul": phishing},
    }}


class FakeRouter:
    def __init__(self, results):
        self.results, self.calls = results, []

    def predict_batch(self, requests, batch_size=None):
        self.calls.append(requests)
        return self.results[:len(requests)]


def mail(i, subject, sender="a@b.com", headers=None, labels=None):
    h = {"From": sender, "Subject": subject}
    h.update(headers or {})
    return {"id": str(i), "subject": subject, "from": sender, "body": "hello", "headers": h,
            "labels": labels or ["INBOX", "UNREAD"]}


emails = [
    mail(1, "50% off everything", "deals@shop.com", {"List-Unsubscribe": "<mailto:x>"}),
    mail(2, "Your repayment failed", "alerts@bank.com"),
    mail(3, "Verify your account now", "support@paypa1.xyz"),
    mail(4, "Weekly digest", "noreply@app.com", labels=["INBOX", "STARRED"]),
    mail(5, "Your order shipped", "noreply@store.com"),
    mail(6, "Some update", "noreply@x.com"),
]
router = FakeRouter([
    ans("promo", 0.2), ans("finance", 2.5, action=0.9), ans("security", 1.5, phishing=0.8),
    ans("promo", 0.3), ans("receipt", 0.8), ans("notification", 1.5, conf=0.3),
])
got = EmailSorter(router=router, model="english").sort(emails)
by = {d.id: d for d in got}

assert not by["1"].keep, by["1"]
assert by["2"].keep and by["2"].reason == "finance email"
assert by["3"].keep and by["3"].reason == "security notice"
assert by["4"].keep and by["4"].reason == "starred"
assert not by["5"].keep
assert by["6"].keep and by["6"].reason == "model unsure"
assert all(r["model"] == "english" for r in router.calls[0])
assert set(router.calls[0][0]["questions"]) == {"bucket", "importance", "needs_action", "is_phishing"}
assert EmailSorter(router=router).sort([]) == []

s = header_signals({"From": "No-Reply@x.com", "List-Id": "list"}, ["CATEGORY_PROMOTIONS"])
assert s["noreply"] and s["bulk"] and s["gmail_bulk_category"] and not s["starred"]

import base64  # noqa: E402
data = base64.urlsafe_b64encode(b"<p>Pay RM100 by Friday</p><style>x{}</style>").decode().rstrip("=")
m = parse_message({"id": "9", "labelIds": ["INBOX"], "payload": {
    "headers": [{"name": "Subject", "value": "Bill"}, {"name": "X-Other", "value": "y"}],
    "mimeType": "text/html", "body": {"data": data}}})
assert m["subject"] == "Bill" and "Pay RM100 by Friday" in m["body"] and "X-Other" not in m["headers"]

import inspect  # noqa: E402
from email_sorter import gmail_client  # noqa: E402
src = inspect.getsource(gmail_client)
assert ".delete(" not in src and ".trash(" not in src, "sorter must never delete or trash mail"

print("email_sorter: all checks passed")
