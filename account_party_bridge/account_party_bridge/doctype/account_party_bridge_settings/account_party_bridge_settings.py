import frappe
from frappe.model.document import Document


class AccountPartyBridgeSettings(Document):
	def on_update(self):
		frappe.cache().delete_key("account_party_bridge_maps")


def is_enabled():
	return frappe.db.get_single_value("Account Party Bridge Settings", "enabled")


def suppress_messages():
	return frappe.db.get_single_value("Account Party Bridge Settings", "suppress_messages")
