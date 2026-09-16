import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

# source fieldtype -> target fieldtypes that accept it without surprises
COMPATIBLE = {
	"Data": {"Data", "Small Text", "Text", "Long Text", "Select", "Link", "Read Only"},
	"Small Text": {"Data", "Small Text", "Text", "Long Text"},
	"Text": {"Small Text", "Text", "Long Text"},
	"Link": {"Link", "Data", "Read Only", "Select"},
	"Select": {"Select", "Data", "Small Text"},
	"Read Only": {"Data", "Read Only", "Small Text"},
	"Int": {"Int", "Float", "Data", "Currency"},
	"Float": {"Float", "Currency", "Int"},
	"Currency": {"Currency", "Float"},
	"Percent": {"Percent", "Float"},
	"Check": {"Check", "Int"},
	"Date": {"Date", "Datetime", "Data"},
	"Datetime": {"Datetime", "Date", "Data"},
	"Time": {"Time", "Data"},
}


class AccountPartyMap(Document):
	def validate(self):
		self.validate_group_config()
		self.validate_party_config()
		self.validate_field_mappings()

	def on_update(self):
		frappe.cache().delete_key("account_party_bridge_maps")

	def on_trash(self):
		frappe.cache().delete_key("account_party_bridge_maps")

	# ------------------------------------------------------------
	def validate_group_config(self):
		if not cint(self.create_group_node) or not self.group_doctype:
			return

		meta = frappe.get_meta(self.group_doctype)

		if not meta.get("is_tree"):
			frappe.msgprint(
				_("{0} is not a tree doctype. Parent nesting will not work.").format(self.group_doctype),
				indicator="orange",
				alert=True,
			)

		for fieldname in ("group_name_field", "group_parent_field"):
			value = self.get(fieldname)
			if value and not meta.has_field(value):
				frappe.throw(
					_("{0}: {1} is not a field on {2}").format(
						_(self.meta.get_label(fieldname)), value, self.group_doctype
					)
				)

	# ------------------------------------------------------------
	def validate_party_config(self):
		if not cint(self.create_leaf_party) or not self.party_doctype:
			return

		meta = frappe.get_meta(self.party_doctype)

		for fieldname in ("party_name_field", "party_group_field", "party_naming_field"):
			value = self.get(fieldname)
			if not value:
				continue

			# naming field points at Account, not the party
			target_meta = frappe.get_meta("Account") if fieldname == "party_naming_field" else meta
			target_dt = "Account" if fieldname == "party_naming_field" else self.party_doctype

			if not target_meta.has_field(value):
				frappe.throw(
					_("{0}: {1} is not a field on {2}").format(
						_(self.meta.get_label(fieldname)), value, target_dt
					)
				)

		if self.accounts_table_field:
			df = meta.get_field(self.accounts_table_field)
			if not df:
				frappe.throw(
					_("Accounts Table Field: {0} is not a field on {1}").format(
						self.accounts_table_field, self.party_doctype
					)
				)
			if df.fieldtype != "Table":
				frappe.throw(
					_("Accounts Table Field: {0} is a {1}, expected a Table").format(
						self.accounts_table_field, df.fieldtype
					)
				)

	# ------------------------------------------------------------
	def validate_field_mappings(self):
		if not self.field_mappings:
			return

		account_meta = frappe.get_meta("Account")
		party_meta = frappe.get_meta(self.party_doctype) if self.party_doctype else None

		seen = set()

		for row in self.field_mappings:
			if row.target_field in seen:
				frappe.throw(_("Row {0}: duplicate target field {1}").format(row.idx, row.target_field))
			seen.add(row.target_field)

			if party_meta and not party_meta.has_field(row.target_field):
				frappe.throw(
					_("Row {0}: {1} is not a field on {2}").format(
						row.idx, row.target_field, self.party_doctype
					)
				)

			if row.mapping_type == "Account Field":
				if not row.source_field:
					frappe.throw(_("Row {0}: Source Field is required for Account Field mapping").format(row.idx))

				if not account_meta.has_field(row.source_field):
					frappe.throw(_("Row {0}: {1} is not a field on Account").format(row.idx, row.source_field))

				if party_meta:
					self.warn_on_type_mismatch(row, account_meta, party_meta)

			elif not row.static_value:
				frappe.throw(_("Row {0}: Value is required for {1} mapping").format(row.idx, row.mapping_type))

	# ------------------------------------------------------------
	def warn_on_type_mismatch(self, row, account_meta, party_meta):
		source_type = account_meta.get_field(row.source_field).fieldtype
		target_type = party_meta.get_field(row.target_field).fieldtype

		if source_type == target_type:
			return

		allowed = COMPATIBLE.get(source_type, {source_type})

		if target_type not in allowed:
			frappe.msgprint(
				_("Row {0}: {1} ({2}) into {3} ({4}) may not convert cleanly").format(
					row.idx, row.source_field, source_type, row.target_field, target_type
				),
				indicator="orange",
				alert=True,
			)


# ------------------------------------------------------------
# Whitelisted endpoints
# ------------------------------------------------------------
@frappe.whitelist()
def backfill(map_name, limit=None):
	"""Apply one map to accounts that already exist. Idempotent."""
	frappe.only_for(("System Manager", "Accounts Manager"))

	from account_party_bridge.utils.bridge import apply_map

	cfg = frappe.get_doc("Account Party Map", map_name)

	if not cint(cfg.enabled):
		frappe.throw(_("Map {0} is disabled").format(map_name))

	names = frappe.get_all(
		"Account",
		filters={"account_type": cfg.account_type},
		order_by="lft asc",
		limit_page_length=int(limit) if limit else 0,
		pluck="name",
	)

	created = 0
	skipped = 0
	failed = []

	for name in names:
		account = frappe.get_doc("Account", name)
		try:
			if apply_map(account, cfg):
				created += 1
			else:
				skipped += 1
		except Exception:
			failed.append(name)
			frappe.log_error(
				title="Account Party Bridge backfill failed",
				message=f"{name}\n\n{frappe.get_traceback()}",
			)

	frappe.db.commit()

	return {
		"total": len(names),
		"created": created,
		"skipped": skipped,
		"failed": failed,
	}
