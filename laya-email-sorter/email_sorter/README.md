# email_sorter

A Gmail inbox sorter that uses laya as a System 1 decision model: no LLM calls, no text
generation, one fast forward pass per email on your own machine.

## How it decides

1. **Header rules** (free): mailing-list headers, no-reply senders, Gmail's Promotions/Social
   labels, starred mail.
2. **One laya pass** answers four typed questions per email:
   - `bucket` - action / finance / personal / work / security / receipt / notification / promo
   - `importance` - 0 (safe to ignore) to 3 (must act)
   - `needs_action` - probability you need to pay, reply, sign or confirm
   - `is_phishing` - probability it's a scam
3. **Cautious policy**: starred, possible phishing, needs-action, finance, personal and work
   mail always stays. Anything the model is unsure about stays. Only low-importance promos,
   notifications and receipts get archived.

## Safety

- Dry run by default. It prints a summary and writes `sort_report.csv`; Gmail is untouched.
- `--apply` asks you to type `archive` first, then only removes the INBOX label. Archived mail
  stays in All Mail and search. There is no delete or trash code, and a test checks that.
- The dry run uses the read-only Gmail scope. Write access is requested only for `--apply`.

## Setup

```bash
pip install -e . google-api-python-client google-auth-oauthlib
# Google Cloud console: enable the Gmail API, create an OAuth client (Desktop app),
# download it as credentials.json into this folder.
python -m email_sorter --limit 200            # dry run
python -m email_sorter --limit 200 --apply    # archive after you confirm
```

The first run downloads a laya checkpoint from Hugging Face (421M parameters for English,
322M for multilingual). A GPU is optional; on CPU it is slower but fine for a few hundred
emails. Malay and other non-English mail is routed to `laya-multilingual` automatically.

## Tuning

Edit `BUCKETS`, `ALWAYS_KEEP` and the thresholds in `sorter.py`. For better accuracy, label a
few hundred of your own emails from `sort_report.csv` and fine-tune with laya's notebook.

## Tests

```bash
python tests/test_email_sorter.py   # no model or network needed
```
