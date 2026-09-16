# Account Party Bridge

Create a Customer or Supplier automatically when someone adds a Receivable or
Payable account to the Chart of Accounts. Group accounts mirror into Customer
Group / Supplier Group nodes, so the party tree matches the account tree.

Which fields carry across is configuration, not code. Every field on Account and
on the party doctype is offered in a dropdown, custom fields included.

Built for Frappe v15 / ERPNext v15.

## Install

```bash
cd ~/frappe-bench
bench get-app https://github.com/YOURORG/account_party_bridge.git
bench --site YOURSITE install-app account_party_bridge
```

From a local folder instead:

```bash
bench get-app /path/to/account_party_bridge
bench --site YOURSITE install-app account_party_bridge
```

Install seeds two maps, Receivable and Payable, with ERPNext defaults. Nothing
else to run.

## Update

```bash
cd ~/frappe-bench/apps/account_party_bridge
git pull
cd ~/frappe-bench
bench --site YOURSITE migrate
bench restart
```

## Uninstall

```bash
bench --site YOURSITE uninstall-app account_party_bridge
```

Removes the maps. Customers and Suppliers already created stay put.

## What it does

```
Accounts Receivable      group, Receivable  ->  Customer Group "Accounts Receivable"
  Trade Debtors          group, Receivable  ->  Customer Group "Trade Debtors"
    ACME Corp            leaf,  Receivable  ->  Customer "ACME Corp"
                                                 accounts row: ACME Corp - XX
```

Payable mirrors into Supplier Group / Supplier the same way.

Because the Party Account row is filled in, Sales Invoice picks up
`ACME Corp - XX` as Debit To instead of the shared `Debtors - XX`.

## Configure

**Account Party Map** list, one row per account type.

### Trigger

| Field | Meaning |
|---|---|
| Account Type | Must match `Account.account_type` exactly |
| Enabled | Off switch for this type |
| Create Group from Group Account | Mirror `is_group = 1` accounts into the tree |
| Create Party from Leaf Account | Mirror `is_group = 0` accounts into parties |
| Sync Party on Account Update | Push later edits to the linked party |

### Group Account Mapping

| Field | Example |
|---|---|
| Group DocType | `Customer Group` |
| Group Name Field | `customer_group_name` |
| Group Parent Field | `parent_customer_group` |
| Root Group | `All Customer Groups` |

Root Group is the fallback parent when the account's parent has no mirror yet.

### Leaf Account Mapping

| Field | Example |
|---|---|
| Party DocType | `Customer` |
| Party Name Field | `customer_name` |
| Party Group Field | `customer_group` |
| Accounts Table Field | `accounts`, blank to skip binding |
| Party Naming Field | `account_number`, blank for ERPNext default naming |
| Append Company Abbr to Name | For multi-company code collisions |

Set Party Naming Field to `account_number` if you want the party ID to be the
account code rather than the name.

### Field Mapping

The table that does the real work. One row per field you want carried across.

| Column | Meaning |
|---|---|
| Mapping Type | `Account Field`, `Static`, `Global Default`, `Eval` |
| Source Field | Account fieldname. Only for `Account Field` |
| Value | Literal, default key, or python expression |
| Target Field | Party fieldname |
| Mandatory | Throw if the value resolves empty |
| Overwrite on Sync | Also update on later Account edits |

Both dropdowns are built from live metadata, so a Custom Field added yesterday
shows up today. Custom fields are marked with an asterisk.

`Eval` runs through `frappe.safe_eval` with `doc`, `account`, `party` and
`frappe` in scope:

```
doc.account_currency or "SAR"
```

Save warns when a source and target fieldtype pair looks lossy. It does not
block you.

## Backfill

Open a map, click **Backfill Existing Accounts**. Walks every account of that
type in tree order so parents are created before children. Safe to run more
than once, existing parties are skipped.

Skipped and failed counts come back in the dialog. Failures land in Error Log.

Or from the console:

```python
from account_party_bridge.account_party_bridge.doctype.account_party_map.account_party_map import backfill
backfill("Receivable")
```

## Global switch

**Account Party Bridge Settings** has one Enabled checkbox that halts all
mirroring without touching individual maps. Handy during a data import.

## Design note

ERPNext's normal flow is the reverse of this. One `Debtors` account is shared by
every customer, and the ledger is split by the `party` field on GL Entry. That
scales better and keeps the Trial Balance readable.

Per-party accounts are worth the chart bloat when a regulator or auditor wants
account-level party ledgers. If nobody is asking for that, the stock
Accounts Receivable report already gives you the same information.

## Gotchas

- Create the parent group account before its children, or the mirror lands under Root Group.
- `account_number` is optional in ERPNext. Blank means default naming applies.
- Deleting an Account that a party links to raises `LinkExistsError`. Expected.
- Same account name in two companies produces one party. Turn on Append Company Abbr.
- Numeric docnames sort as text in Link fields. Zero-pad codes if that bothers you.
- If the group tree looks wrong after a bulk import, use the Rebuild Group Tree button.

## Tests

```bash
bench --site YOURSITE set-config allow_tests true
bench --site YOURSITE run-tests --app account_party_bridge
```

## Layout

```
account_party_bridge/
├── hooks.py                     doc_events on Account
├── install.py                   after_install / before_uninstall
├── patches/v0_0_1/
│   └── seed_default_maps.py     idempotent defaults
├── utils/
│   ├── bridge.py                mirroring logic
│   └── meta.py                  whitelisted field discovery
└── account_party_bridge/doctype/
    ├── account_party_map/       parent config
    ├── account_party_field_map/ child field map
    └── account_party_bridge_settings/
```

## License

MIT
