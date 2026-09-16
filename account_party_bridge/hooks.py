app_name = "account_party_bridge"
app_title = "Account Party Bridge"
app_publisher = "Your Company"
app_description = "Mirror Chart of Accounts Receivable/Payable nodes into Customer/Supplier masters"
app_email = "you@example.com"
app_license = "mit"

required_apps = ["frappe/erpnext"]

# ------------------------------------------------------------
# Document Events
# ------------------------------------------------------------
doc_events = {
	"Account": {
		"after_insert": "account_party_bridge.utils.bridge.on_account_insert",
		"on_update": "account_party_bridge.utils.bridge.on_account_update",
	}
}

# ------------------------------------------------------------
# Install / Uninstall
# ------------------------------------------------------------
after_install = "account_party_bridge.install.after_install"
before_uninstall = "account_party_bridge.install.before_uninstall"

# ------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------
fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [["module", "=", "Account Party Bridge"]],
	}
]
