import frappe


def after_install():
	from account_party_bridge.patches.v0_0_1.seed_default_maps import execute as seed

	seed()

	frappe.db.commit()

	print("")
	print("  Account Party Bridge installed.")
	print("  Default maps seeded for Receivable and Payable.")
	print("  Open the Account Party Map list to adjust field mappings.")
	print("")


def before_uninstall():
	"""Leave created parties alone. Only remove config."""
	for name in frappe.get_all("Account Party Map", pluck="name"):
		frappe.delete_doc("Account Party Map", name, force=1, ignore_permissions=True)

	frappe.cache().delete_key("account_party_bridge_maps")
	frappe.db.commit()
