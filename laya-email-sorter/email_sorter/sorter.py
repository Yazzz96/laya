"""Turn laya answers plus header signals into a keep/archive decision."""
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from laya.email import email_state

from .rules import header_signals

BUCKETS = {
    "action": "asks the reader to do, decide, sign, confirm or reply to something",
    "finance": "bills, payment due or failed, bank, loan, credit card, pay later, tax, salary",
    "personal": "a real person writing to the reader personally: friends, family, dates, plans",
    "work": "job, colleagues, clients, projects, interviews, recruiters",
    "security": "sign-in alerts, password or 2FA codes, account security notices",
    "receipt": "order confirmation, receipt, shipping or delivery update",
    "notification": "automated app or service update that needs no action",
    "promo": "newsletter, marketing, sale, promotion, social media digest",
}


def sort_questions() -> Dict[str, Dict[str, Any]]:
    """The questions answered for every email, in a single forward pass."""
    return {
        "bucket": {"type": "choice", "instructions": "What kind of email is this?", "criteria": dict(BUCKETS)},
        "importance": {"type": "score", "instructions": "How much does the reader need to see this email?",
                       "criteria": ["safe to ignore", "nice to know", "should read", "must act"]},
        "needs_action": {"type": "noul",
                         "instructions": "Does the reader need to do something, such as pay, reply, sign or confirm?"},
        "is_phishing": {"type": "noul",
                        "instructions": "Is this email a phishing or scam attempt to steal money, credentials, "
                                        "or personal data?",
                        "criteria": {"true": "phishing, scam, or fraud", "false": "a legitimate email"}},
    }


# Buckets that are never archived automatically, whatever the model scores.
ALWAYS_KEEP = {"action", "finance", "personal", "work"}


@dataclass
class Decision:
    id: str
    subject: str
    sender: str
    bucket: str
    importance: float
    needs_action: float
    phishing: float
    keep: bool
    reason: str
    confidence: float
    signals: Dict[str, bool] = field(default_factory=dict)

    def to_row(self) -> Dict[str, Any]:
        row = asdict(self)
        row.pop("signals")
        return row


class EmailSorter:
    """Sort emails with a laya Router (or any object with the same `predict_batch`).

    Thresholds are deliberately cautious: when unsure, keep the email in the inbox.
    """

    def __init__(self, router: Optional[Any] = None, archive_below: float = 1.5,
                 action_threshold: float = 0.5, min_confidence: float = 0.6,
                 router_factory: Optional[Callable[[], Any]] = None, model: Optional[str] = None,
                 max_loaded: int = 2):
        self.model = model
        self.max_loaded = max_loaded
        self._router = router
        self._factory = router_factory
        self.archive_below = archive_below
        self.action_threshold = action_threshold
        self.min_confidence = min_confidence

    @property
    def router(self):
        if self._router is None:
            if self._factory is not None:
                self._router = self._factory()
            else:
                from laya import Router
                self._router = Router(max_loaded=self.max_loaded)
        return self._router

    def decide(self, email: Dict[str, Any], answers: Dict[str, Any]) -> Decision:
        signals = header_signals(email.get("headers", {}), email.get("labels", []))
        bucket = answers["bucket"]["choice"]
        conf = float(answers["bucket"].get("answer_confidence", answers["bucket"].get("confidence", 0.0)))
        importance = float(answers["importance"]["score"])
        action = float(answers["needs_action"]["noul"])
        phishing = float(answers["is_phishing"]["noul"])

        # The typed `bucket` choice is the decision signal. On the shipped zero-shot checkpoints the
        # yes/no answers (phishing, needs-action) run hot on ordinary mail, so they are reported as
        # hints and only break ties; fine-tune before letting them drive archiving.
        bulk = signals["bulk"] or signals["gmail_bulk_category"]
        if signals["starred"]:
            keep, reason = True, "starred"
        elif conf < self.min_confidence:
            keep, reason = True, "model unsure"
        elif bucket in ALWAYS_KEEP:
            keep, reason = True, f"{bucket} email"
        elif bucket == "security":
            keep, reason = True, "security notice"
        elif bucket == "promo":
            keep, reason = False, "promo"
        elif bucket in ("notification", "receipt") and (bulk or importance < self.archive_below):
            keep, reason = False, f"low-signal {bucket}"
        elif action >= self.action_threshold and importance >= 2.0:
            keep, reason = True, "needs action"
        else:
            keep, reason = True, f"{bucket}, importance {importance:.1f}"

        return Decision(id=email["id"], subject=email.get("subject", ""), sender=email.get("from", ""),
                        bucket=bucket, importance=round(importance, 2), needs_action=round(action, 2),
                        phishing=round(phishing, 2), keep=keep, reason=reason, confidence=round(conf, 2),
                        signals=signals)

    def sort(self, emails: List[Dict[str, Any]], batch_size: int = 16) -> List[Decision]:
        questions = sort_questions()
        requests = [{"state": email_state(e.get("subject", ""), e.get("body", ""), sender=e.get("from")),
                     "questions": questions} for e in emails]
        if self.model:
            for r in requests:
                r["model"] = self.model
        if not requests:
            return []
        results = self.router.predict_batch(requests, batch_size=batch_size)
        return [self.decide(e, r["answers"]) for e, r in zip(emails, results)]
