import frappe
from frappe.tests.utils import FrappeTestCase


class TestAccountPartyMap(FrappeTestCase):
	def setUp(self):
		self.company = frappe.db.get_value("Company", {}, "name")
		self.abbr = frappe.get_cached_value("Company", self.company, "abbr")

	def tearDown(self):
		frappe.db.rollback()

	# ------------------------------------------------------------
	def test_default_maps_seeded(self):
		self.assertTrue(frappe.db.exists("Account Party Map", "Receivable"))
		self.assertTrue(frappe.db.exists("Account Party Map", "Payable"))

	# ------------------------------------------------------------
	def test_bad_target_field_rejected(self):
		cfg = frappe.get_doc("Account Party Map", "Receivable")
		cfg.append(
			"field_mappings",
			{
				"mapping_type": "Static",
				"static_value": "x",
				"target_field": "this_field_does_not_exist",
			},
		)

		self.assertRaises(frappe.ValidationError, cfg.save)

	# ------------------------------------------------------------
	def test_duplicate_target_field_rejected(self):
		cfg = frappe.get_doc("Account Party Map", "Receivable")
		cfg.field_mappings = []
		cfg.append(
			"field_mappings",
			{"mapping_type": "Static", "static_value": "Company", "target_field": "customer_type"},
		)
		cfg.append(
			"field_mappings",
			{"mapping_type": "Static", "static_value": "Individual", "target_field": "customer_type"},
		)

		self.assertRaises(frappe.ValidationError, cfg.save)

	# ------------------------------------------------------------
	def test_leaf_account_creates_customer(self):
		parent = frappe.db.get_value(
			"Account",
			{"company": self.company, "account_type": "Receivable", "is_group": 1},
			"name",
		) or frappe.db.get_value(
			"Account", {"company": self.company, "root_type": "Asset", "is_group": 1}, "name"
		)

		account = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": "Test Bridge Customer",
				"parent_account": parent,
				"company": self.company,
				"account_type": "Receivable",
				"is_group": 0,
			}
		).insert()

		self.assertTrue(frappe.db.exists("Customer", {"customer_name": "Test Bridge Customer"}))

		customer = frappe.get_doc("Customer", {"customer_name": "Test Bridge Customer"})
		accounts = [d.account for d in customer.accounts]

		self.assertIn(account.name, accounts)
		self.assertEqual(customer.customer_type, "Company")

	# ------------------------------------------------------------
	def test_second_run_is_idempotent(self):
		from account_party_bridge.utils.bridge import apply_map

		parent = frappe.db.get_value(
			"Account", {"company": self.company, "root_type": "Asset", "is_group": 1}, "name"
		)

		account = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": "Test Bridge Idempotent",
				"parent_account": parent,
				"company": self.company,
				"account_type": "Receivable",
				"is_group": 0,
			}
		).insert()

		cfg = frappe.get_doc("Account Party Map", "Receivable")

		# already created by the hook, so a manual re-run must do nothing
		self.assertFalse(apply_map(account, cfg))

	# ------------------------------------------------------------
	def test_disabled_map_does_nothing(self):
		cfg = frappe.get_doc("Account Party Map", "Receivable")
		cfg.enabled = 0
		cfg.save()

		parent = frappe.db.get_value(
			"Account", {"company": self.company, "root_type": "Asset", "is_group": 1}, "name"
		)

		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": "Test Bridge Disabled",
				"parent_account": parent,
				"company": self.company,
				"account_type": "Receivable",
				"is_group": 0,
			}
		).insert()

		self.assertFalse(frappe.db.exists("Customer", {"customer_name": "Test Bridge Disabled"}))
