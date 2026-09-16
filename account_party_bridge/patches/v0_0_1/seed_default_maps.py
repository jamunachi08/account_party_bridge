import frappe

DEFAULTS = [
	{
		"doctype": "Account Party Map",
		"account_type": "Receivable",
		"enabled": 1,
		"create_group_node": 1,
		"create_leaf_party": 1,
		"sync_on_rename": 0,
		"group_doctype": "Customer Group",
		"group_name_field": "customer_group_name",
		"group_parent_field": "parent_customer_group",
		"root_group": "All Customer Groups",
		"party_doctype": "Customer",
		"party_name_field": "customer_name",
		"party_group_field": "customer_group",
		"accounts_table_field": "accounts",
		"party_naming_field": "",
		"append_company_abbr": 0,
		"field_mappings": [
			{
				"mapping_type": "Static",
				"static_value": "Company",
				"target_field": "customer_type",
				"mandatory": 1,
			},
			{
				"mapping_type": "Global Default",
				"static_value": "territory",
				"target_field": "territory",
				"mandatory": 0,
			},
			{
				"mapping_type": "Account Field",
				"source_field": "account_currency",
				"target_field": "default_currency",
				"mandatory": 0,
				"overwrite_on_sync": 0,
			},
			{
				"mapping_type": "Account Field",
				"source_field": "disabled",
				"target_field": "disabled",
				"mandatory": 0,
				"overwrite_on_sync": 1,
			},
		],
	},
	{
		"doctype": "Account Party Map",
		"account_type": "Payable",
		"enabled": 1,
		"create_group_node": 1,
		"create_leaf_party": 1,
		"sync_on_rename": 0,
		"group_doctype": "Supplier Group",
		"group_name_field": "supplier_group_name",
		"group_parent_field": "parent_supplier_group",
		"root_group": "All Supplier Groups",
		"party_doctype": "Supplier",
		"party_name_field": "supplier_name",
		"party_group_field": "supplier_group",
		"accounts_table_field": "accounts",
		"party_naming_field": "",
		"append_company_abbr": 0,
		"field_mappings": [
			{
				"mapping_type": "Static",
				"static_value": "Company",
				"target_field": "supplier_type",
				"mandatory": 1,
			},
			{
				"mapping_type": "Account Field",
				"source_field": "account_currency",
				"target_field": "default_currency",
				"mandatory": 0,
				"overwrite_on_sync": 0,
			},
			{
				"mapping_type": "Account Field",
				"source_field": "disabled",
				"target_field": "disabled",
				"mandatory": 0,
				"overwrite_on_sync": 1,
			},
		],
	},
]


def execute():
	"""Seed default maps. Idempotent, never overwrites user edits."""
	for row in DEFAULTS:
		if frappe.db.exists("Account Party Map", row["account_type"]):
			continue

		doc = frappe.get_doc(row)
		doc.flags.ignore_permissions = True

		try:
			doc.insert()
		except Exception:
			frappe.log_error(
				title="Account Party Bridge seed failed",
				message=f"{row['account_type']}\n\n{frappe.get_traceback()}",
			)

	frappe.cache().delete_key("account_party_bridge_maps")
