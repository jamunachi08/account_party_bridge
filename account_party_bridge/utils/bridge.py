import frappe
from frappe import _
from frappe.utils import cint

from account_party_bridge.utils.meta import get_active_maps


# ============================================================
# Hook entry points
# ============================================================
def on_account_insert(doc, method=None):
	"""Account after_insert. Mirror into party master."""
	cfg = get_map_for(doc)

	if not cfg:
		return

	try:
		apply_map(doc, cfg)
	except Exception:
		frappe.log_error(
			title="Account Party Bridge insert failed",
			message=f"{doc.name}\n\n{frappe.get_traceback()}",
		)
		frappe.msgprint(
			_("Could not create the linked party for {0}. See Error Log.").format(doc.name),
			indicator="red",
			alert=True,
		)


def on_account_update(doc, method=None):
	"""Account on_update. Push flagged changes to an existing party."""
	if doc.flags.in_insert:
		return

	cfg = get_map_for(doc)

	if not cfg or not cint(cfg.sync_on_rename):
		return

	try:
		sync_party(doc, cfg)
	except Exception:
		frappe.log_error(
			title="Account Party Bridge sync failed",
			message=f"{doc.name}\n\n{frappe.get_traceback()}",
		)


# ============================================================
# Map resolution
# ============================================================
def get_map_for(account):
	"""Return the enabled map for this account's type, or None."""
	if not account.account_type:
		return None

	if not frappe.db.get_single_value("Account Party Bridge Settings", "enabled"):
		return None

	if account.account_type not in get_active_maps():
		return None

	name = frappe.db.get_value(
		"Account Party Map",
		{"account_type": account.account_type, "enabled": 1},
		"name",
	)

	if not name:
		return None

	return frappe.get_cached_doc("Account Party Map", name)


# ============================================================
# Main worker
# ============================================================
def apply_map(account, cfg):
	"""Create the group node or party for one account.

	Returns True if something was created, False if it already existed
	or the map is configured to skip this kind of account.
	"""
	# Check fields are not cast in memory, only on db write. A tree UI post can
	# leave is_group as the string "0", which is truthy in Python.
	if cint(account.is_group):
		if not cint(cfg.create_group_node) or not cfg.group_doctype:
			return False
		return create_group_node(account, cfg)

	if not cint(cfg.create_leaf_party) or not cfg.party_doctype:
		return False

	return create_party(account, cfg)


# ============================================================
# Group node
# ============================================================
def create_group_node(account, cfg):
	label = (account.account_name or "").strip()

	if not label:
		return False

	if frappe.db.exists(cfg.group_doctype, {cfg.group_name_field: label}):
		return False

	node = frappe.new_doc(cfg.group_doctype)
	node.set(cfg.group_name_field, label)
	node.set(cfg.group_parent_field, resolve_parent_group(account, cfg))
	node.is_group = 1

	node.flags.ignore_permissions = True
	node.insert()

	frappe.msgprint(
		_("{0} {1} created from account {2}").format(cfg.group_doctype, node.name, account.name),
		indicator="green",
		alert=True,
	)

	return True


def resolve_parent_group(account, cfg):
	"""Find the group node mirroring this account's parent. Fall back to root."""
	if not account.parent_account:
		return cfg.root_group

	parent_label = frappe.db.get_value("Account", account.parent_account, "account_name")

	if not parent_label:
		return cfg.root_group

	found = frappe.db.get_value(
		cfg.group_doctype,
		{cfg.group_name_field: parent_label.strip()},
		"name",
	)

	return found or cfg.root_group


# ============================================================
# Party
# ============================================================
def create_party(account, cfg):
	label = (account.account_name or "").strip()

	if not label:
		return False

	forced_name = build_party_name(account, cfg)

	if party_exists(account, cfg, label, forced_name):
		return False

	party = frappe.new_doc(cfg.party_doctype)
	party.set(cfg.party_name_field, label)

	if cfg.party_group_field:
		party.set(cfg.party_group_field, resolve_parent_group(account, cfg))

	apply_field_mappings(account, cfg, party)
	bind_account(account, cfg, party)

	if forced_name:
		party.name = forced_name
		party.flags.name_set = True

	party.flags.ignore_permissions = True
	party.flags.from_account_party_bridge = True
	party.insert()

	frappe.msgprint(
		_("{0} {1} created from account {2}").format(cfg.party_doctype, party.name, account.name),
		indicator="green",
		alert=True,
	)

	return True


def party_exists(account, cfg, label, forced_name):
	"""Already linked, already named, or already titled the same."""
	if cfg.accounts_table_field:
		child_dt = frappe.get_meta(cfg.party_doctype).get_field(cfg.accounts_table_field).options
		linked = frappe.db.get_value(
			child_dt,
			{"account": account.name, "parenttype": cfg.party_doctype},
			"parent",
		)
		if linked:
			return True

	if forced_name and frappe.db.exists(cfg.party_doctype, forced_name):
		return True

	if not forced_name and frappe.db.exists(cfg.party_doctype, {cfg.party_name_field: label}):
		return True

	return False


def build_party_name(account, cfg):
	"""Docname from an Account field, e.g. account_number. None = default naming."""
	if not cfg.party_naming_field:
		return None

	code = account.get(cfg.party_naming_field)

	if not code:
		return None

	name = str(code).strip()

	if cint(cfg.append_company_abbr) and account.company:
		abbr = frappe.get_cached_value("Company", account.company, "abbr")
		if abbr:
			name = f"{name} - {abbr}"

	return name


def bind_account(account, cfg, party):
	"""Append the Party Account row so invoices post to this account."""
	if not cfg.accounts_table_field:
		return

	party.append(
		cfg.accounts_table_field,
		{"company": account.company, "account": account.name},
	)


# ============================================================
# Field mappings
# ============================================================
def apply_field_mappings(account, cfg, party):
	for row in cfg.field_mappings or []:
		value = resolve_value(account, party, row)

		if value in (None, ""):
			if cint(row.mandatory):
				frappe.throw(
					_("Field map row {0}: {1} resolved empty but is mandatory").format(
						row.idx, row.target_field
					)
				)
			continue

		party.set(row.target_field, value)


def resolve_value(account, party, row):
	if row.mapping_type == "Account Field":
		return account.get(row.source_field)

	if row.mapping_type == "Static":
		return row.static_value

	if row.mapping_type == "Global Default":
		return frappe.db.get_default(row.static_value)

	if row.mapping_type == "Eval":
		return eval_expression(row.static_value, account, party)

	return None


def eval_expression(expression, account, party):
	if not expression:
		return None

	try:
		return frappe.safe_eval(
			expression,
			None,
			{"doc": account, "account": account, "party": party, "frappe": frappe},
		)
	except Exception:
		frappe.log_error(
			title="Account Party Bridge eval failed",
			message=f"{expression}\n\n{frappe.get_traceback()}",
		)
		return None


# ============================================================
# Sync on update
# ============================================================
def sync_party(account, cfg):
	"""Push flagged field changes to the already-linked party."""
	if not cfg.accounts_table_field or not cfg.party_doctype:
		return

	child_dt = frappe.get_meta(cfg.party_doctype).get_field(cfg.accounts_table_field).options

	party_name = frappe.db.get_value(
		child_dt,
		{"account": account.name, "parenttype": cfg.party_doctype},
		"parent",
	)

	if not party_name:
		return

	party = frappe.get_doc(cfg.party_doctype, party_name)
	changed = False

	before = account.get_doc_before_save()

	# account_name -> party name field
	if before and before.account_name != account.account_name:
		party.set(cfg.party_name_field, (account.account_name or "").strip())
		changed = True

	for row in cfg.field_mappings or []:
		if not cint(row.overwrite_on_sync):
			continue

		value = resolve_value(account, party, row)

		if value in (None, ""):
			continue

		if party.get(row.target_field) != value:
			party.set(row.target_field, value)
			changed = True

	if not changed:
		return

	party.flags.ignore_permissions = True
	party.flags.from_account_party_bridge = True
	party.save()

	frappe.msgprint(
		_("{0} {1} synced from account {2}").format(cfg.party_doctype, party.name, account.name),
		indicator="blue",
		alert=True,
	)
