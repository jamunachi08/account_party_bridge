import frappe
from frappe import _
from frappe.utils import cint

from account_party_bridge.utils.bridge import apply_map


@frappe.whitelist()
def find_misrouted(map_name, delete_groups=0):
	"""Find leaf accounts that were mirrored into a group node by mistake.

	The old is_group truthiness bug sent every account down the group branch.
	This locates the stray group nodes, optionally deletes the childless ones,
	and reports which accounts still have no party.
	"""
	frappe.only_for("System Manager")

	delete_groups = cint(delete_groups)
	cfg = frappe.get_doc("Account Party Map", map_name)

	leaf_accounts = frappe.get_all(
		"Account",
		filters={"account_type": cfg.account_type, "is_group": 0},
		fields=["name", "account_name", "company"],
		order_by="lft asc",
	)

	child_dt = None
	if cfg.accounts_table_field:
		child_dt = frappe.get_meta(cfg.party_doctype).get_field(cfg.accounts_table_field).options

	stray_groups = []
	missing_parties = []
	deleted = []
	kept = []

	for account in leaf_accounts:
		label = (account.account_name or "").strip()

		# a group node named after a leaf account is a symptom of the bug
		group_name = frappe.db.get_value(
			cfg.group_doctype, {cfg.group_name_field: label}, "name"
		)

		if group_name:
			stray_groups.append(group_name)

		has_party = False

		if child_dt:
			has_party = bool(
				frappe.db.get_value(
					child_dt,
					{"account": account.name, "parenttype": cfg.party_doctype},
					"parent",
				)
			)

		if not has_party:
			has_party = bool(
				frappe.db.exists(cfg.party_doctype, {cfg.party_name_field: label})
			)

		if not has_party:
			missing_parties.append(account.name)

	if delete_groups:
		for group_name in stray_groups:
			if has_dependents(cfg, group_name):
				kept.append(group_name)
				continue

			try:
				frappe.delete_doc(cfg.group_doctype, group_name, ignore_permissions=True)
				deleted.append(group_name)
			except Exception:
				kept.append(group_name)
				frappe.log_error(
					title="Account Party Bridge cleanup failed",
					message=f"{group_name}\n\n{frappe.get_traceback()}",
				)

		frappe.db.commit()

	return {
		"leaf_accounts": len(leaf_accounts),
		"stray_groups": stray_groups,
		"deleted": deleted,
		"kept_in_use": kept,
		"missing_parties": missing_parties,
	}


def has_dependents(cfg, group_name):
	"""True if the group node has children or is referenced by a party."""
	if frappe.db.exists(cfg.group_doctype, {cfg.group_parent_field: group_name}):
		return True

	if cfg.party_group_field and frappe.db.exists(
		cfg.party_doctype, {cfg.party_group_field: group_name}
	):
		return True

	return False


@frappe.whitelist()
def repair(map_name, delete_groups=1):
	"""Full repair: drop stray group nodes, then create the missing parties."""
	frappe.only_for("System Manager")

	cfg = frappe.get_doc("Account Party Map", map_name)

	if not cint(cfg.enabled):
		frappe.throw(_("Map {0} is disabled").format(map_name))

	report = find_misrouted(map_name, delete_groups=delete_groups)

	created = 0
	failed = []

	for account_name in report["missing_parties"]:
		account = frappe.get_doc("Account", account_name)

		try:
			if apply_map(account, cfg):
				created += 1
		except Exception:
			failed.append(account_name)
			frappe.log_error(
				title="Account Party Bridge repair failed",
				message=f"{account_name}\n\n{frappe.get_traceback()}",
			)

	frappe.db.commit()

	report["created"] = created
	report["failed"] = failed

	return report
