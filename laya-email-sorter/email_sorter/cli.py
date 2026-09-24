"""python -m email_sorter  -- dry run by default; --apply archives after you confirm."""
import argparse
import csv
import json
import sys
from collections import Counter

from .sorter import EmailSorter


def report(decisions, out_csv):
    with open(out_csv, "w", newline="") as f:
        rows = [d.to_row() for d in decisions]
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    keep = [d for d in decisions if d.keep]
    arch = [d for d in decisions if not d.keep]
    print(f"\n{len(decisions)} emails: keep {len(keep)}, archive {len(arch)}  (full list: {out_csv})")
    print("By bucket:", dict(Counter(d.bucket for d in decisions)))
    top = sorted(keep, key=lambda d: (d.phishing < 0.5, -d.needs_action, -d.importance))[:15]
    print("\nTop of the pile:")
    for d in top:
        print(f"  [{d.reason}] {d.sender[:40]} - {d.subject[:70]}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="email_sorter", description=__doc__)
    p.add_argument("--query", default="in:inbox", help="Gmail search query (default: in:inbox)")
    p.add_argument("--limit", type=int, default=500)
    p.add_argument("--credentials", default="credentials.json")
    p.add_argument("--out", default="sort_report.csv")
    p.add_argument("--from-json", help="sort emails from a JSON file instead of Gmail (offline test)")
    p.add_argument("--model", choices=["english", "multilingual"], default=None,
                   help="force a checkpoint; default lets laya's router pick per email")
    p.add_argument("--low-memory", action="store_true",
                   help="bf16 weights, one checkpoint in memory at a time (fits ~2 GB RAM, CPU only)")
    p.add_argument("--apply", action="store_true", help="archive the 'archive' emails (asks first)")
    a = p.parse_args(argv)

    if a.from_json:
        with open(a.from_json) as f:
            emails = json.load(f)
        service = None
    else:
        from . import gmail_client
        service = gmail_client.connect(a.credentials, write=False)
        emails = list(gmail_client.inbox_messages(service, a.query, a.limit))

    if a.low_memory:
        from . import lowmem
        lowmem.enable()
    sorter = EmailSorter(model=a.model, max_loaded=1 if a.low_memory else 2)
    decisions = sorter.sort(emails)
    report(decisions, a.out)

    to_archive = [d.id for d in decisions if not d.keep]
    if not a.apply or not to_archive:
        print("\nDry run. Nothing changed in Gmail.")
        return 0
    if a.from_json:
        print("--apply needs Gmail, not --from-json.")
        return 1
    answer = input(f"\nArchive {len(to_archive)} emails? Nothing is deleted. Type 'archive' to confirm: ")
    if answer.strip().lower() != "archive":
        print("Cancelled. Nothing changed.")
        return 0
    from . import gmail_client
    n = gmail_client.archive(gmail_client.connect(a.credentials, write=True), to_archive)
    print(f"Archived {n}. Find them any time under All Mail.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
