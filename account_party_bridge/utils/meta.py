import frappe
from frappe import _

# layout-only fieldtypes carry no value
LAYOUT_TYPES = {
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Button",
	"Fold",
	"Heading",
	"Image",
	"Table Break",
}

# always available, not in meta.fields
VIRTUAL_FIELDS = [
	{"fieldname": "name", "label": "Name (ID)", "fieldtype": "Data"},
	{"fieldname": "owner", "label": "Owner", "fieldtype": "Link", "options": "User"},
	{"fieldname": "creation", "label": "Created On", "fieldtype": "Datetime"},
	{"fieldname": "modified", "label": "Last Modified On", "fieldtype": "Datetime"},
]


@frappe.whitelist()
def get_field_options(doctype, include_tables=0):
	"""Every usable field on a doctype, standard and custom, for map dropdowns."""
	frappe.only_for(("System Manager", "Accounts Manager"))

	if not doctype:
		return []

	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype))

	include_tables = frappe.utils.cint(include_tables)
	meta = frappe.get_meta(doctype)
	out = []

	for df in meta.fields:
		if df.fieldtype in LAYOUT_TYPES:
			continue

		if df.fieldtype in ("Table", "Table MultiSelect") and not include_tables:
			continue

		out.append(
			{
				"fieldname": df.fieldname,
				"label": df.label or df.fieldname,
				"fieldtype": df.fieldtype,
				"options": df.options,
				"reqd": frappe.utils.cint(df.reqd),
				"read_only": frappe.utils.cint(df.read_only),
				"is_custom": frappe.utils.cint(getattr(df, "is_custom_field", 0)),
			}
		)

	for row in VIRTUAL_FIELDS:
		out.append(
			{
				"fieldname": row["fieldname"],
				"label": row["label"],
				"fieldtype": row["fieldtype"],
				"options": row.get("options"),
				"reqd": 0,
				"read_only": 1,
				"is_custom": 0,
			}
		)

	out.sort(key=lambda d: (d["is_custom"], d["label"].lower()))

	return out


@frappe.whitelist()
def rebuild_tree(doctype, parent_field):
	"""Repair nested set left/right values after bulk group creation."""
	frappe.only_for("System Manager")

	from frappe.utils.nestedset import rebuild_tree as _rebuild

	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype))

	meta = frappe.get_meta(doctype)

	if not meta.get("is_tree"):
		frappe.throw(_("{0} is not a tree doctype").format(doctype))

	if not meta.has_field(parent_field):
		frappe.throw(_("{0} is not a field on {1}").format(parent_field, doctype))

	_rebuild(doctype, parent_field)
	frappe.db.commit()

	return True


def get_active_maps():
	"""Cached list of enabled maps keyed by account_type."""
	cached = frappe.cache().get_value("account_party_bridge_maps")

	if cached is not None:
		return cached

	rows = frappe.get_all(
		"Account Party Map",
		filters={"enabled": 1},
		pluck="account_type",
	)

	frappe.cache().set_value("account_party_bridge_maps", rows)

	return rows
