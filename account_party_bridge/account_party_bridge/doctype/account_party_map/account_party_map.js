frappe.ui.form.on("Account Party Map", {
	onload(frm) {
		frm.trigger("load_account_fields");
		frm.trigger("load_group_fields");
		frm.trigger("load_party_fields");
	},

	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Backfill Existing Accounts"), () => {
			frm.trigger("run_backfill");
		});

		frm.add_custom_button(__("Rebuild Group Tree"), () => {
			frm.trigger("rebuild_tree");
		});

		frm.add_custom_button(__("Diagnose Misrouted Accounts"), () => {
			frm.trigger("diagnose");
		});

		if (!frm.doc.enabled) {
			frm.dashboard.set_headline_alert(__("This map is disabled."), "orange");
		}
	},

	group_doctype(frm) {
		frm.set_value("group_name_field", "");
		frm.set_value("group_parent_field", "");
		frm.trigger("load_group_fields");
	},

	party_doctype(frm) {
		frm.set_value("party_name_field", "");
		frm.set_value("party_group_field", "");
		frm.trigger("load_party_fields");
	},

	// ------------------------------------------------------------
	load_account_fields(frm) {
		get_fields("Account").then((fields) => {
			const options = to_select_options(fields);

			set_grid_options(frm, "source_field", options);
			frm.set_df_property("party_naming_field", "options", options);
			frm.refresh_field("party_naming_field");
		});
	},

	load_group_fields(frm) {
		if (!frm.doc.group_doctype) return;

		get_fields(frm.doc.group_doctype).then((fields) => {
			const all = to_select_options(fields);
			const links = to_select_options(fields.filter((d) => d.fieldtype === "Link"));

			frm.set_df_property("group_name_field", "options", all);
			frm.set_df_property("group_parent_field", "options", links.length ? links : all);
			frm.refresh_fields(["group_name_field", "group_parent_field"]);
		});
	},

	load_party_fields(frm) {
		if (!frm.doc.party_doctype) return;

		get_fields(frm.doc.party_doctype).then((fields) => {
			const all = to_select_options(fields);

			set_grid_options(frm, "target_field", all);
			frm.set_df_property("party_name_field", "options", all);
			frm.set_df_property("party_group_field", "options", all);
			frm.refresh_fields(["party_name_field", "party_group_field"]);
		});
	},

	// ------------------------------------------------------------
	run_backfill(frm) {
		frappe.confirm(
			__("Apply this map to all existing {0} accounts? Safe to run more than once.", [
				frm.doc.account_type,
			]),
			() => {
				frappe.call({
					method:
						"account_party_bridge.account_party_bridge.doctype.account_party_map.account_party_map.backfill",
					args: { map_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Backfilling..."),
					callback(r) {
						if (!r.message) return;
						const d = r.message;

						let msg = __("Scanned {0} accounts.", [d.total]);
						msg += "<br>" + __("Created: {0}", [d.created]);
						msg += "<br>" + __("Already existed: {0}", [d.skipped]);

						if (d.failed && d.failed.length) {
							msg +=
								"<br>" +
								__("Failed: {0}", [d.failed.length]) +
								"<br><small>" +
								frappe.utils.escape_html(d.failed.join(", ")) +
								"</small>" +
								"<br><small>" +
								__("See Error Log for details.") +
								"</small>";
						}

						frappe.msgprint({
							title: __("Backfill Complete"),
							message: msg,
							indicator: d.failed && d.failed.length ? "orange" : "green",
						});
					},
				});
			}
		);
	},

	diagnose(frm) {
		frappe.call({
			method: "account_party_bridge.utils.repair.find_misrouted",
			args: { map_name: frm.doc.name, delete_groups: 0 },
			freeze: true,
			freeze_message: __("Scanning..."),
			callback(r) {
				if (!r.message) return;
				const d = r.message;

				let msg = __("Leaf accounts of this type: {0}", [d.leaf_accounts]);
				msg += "<br>" + __("Without a party: {0}", [d.missing_parties.length]);
				msg += "<br>" + __("Group nodes named after a leaf account: {0}", [d.stray_groups.length]);

				if (d.stray_groups.length) {
					msg +=
						"<br><br><small>" +
						frappe.utils.escape_html(d.stray_groups.slice(0, 20).join(", ")) +
						"</small>";
				}

				const dialog = frappe.msgprint({
					title: __("Diagnosis"),
					message: msg,
					indicator: d.missing_parties.length ? "orange" : "green",
					primary_action: d.missing_parties.length
						? {
								label: __("Repair"),
								action() {
									dialog.hide();
									frm.trigger("run_repair");
								},
						  }
						: null,
				});
			},
		});
	},

	run_repair(frm) {
		frappe.confirm(
			__(
				"Delete group nodes that were created from leaf accounts and are not in use, then create the missing parties. Continue?"
			),
			() => {
				frappe.call({
					method: "account_party_bridge.utils.repair.repair",
					args: { map_name: frm.doc.name, delete_groups: 1 },
					freeze: true,
					freeze_message: __("Repairing..."),
					callback(r) {
						if (!r.message) return;
						const d = r.message;

						let msg = __("Parties created: {0}", [d.created]);
						msg += "<br>" + __("Group nodes deleted: {0}", [d.deleted.length]);
						msg += "<br>" + __("Group nodes kept, still in use: {0}", [d.kept_in_use.length]);

						if (d.failed && d.failed.length) {
							msg +=
								"<br>" +
								__("Failed: {0}", [d.failed.length]) +
								"<br><small>" +
								__("See Error Log.") +
								"</small>";
						}

						frappe.msgprint({
							title: __("Repair Complete"),
							message: msg,
							indicator: d.failed && d.failed.length ? "orange" : "green",
						});
					},
				});
			}
		);
	},

	rebuild_tree(frm) {
		if (!frm.doc.group_doctype || !frm.doc.group_parent_field) {
			frappe.msgprint(__("Set Group DocType and Group Parent Field first."));
			return;
		}

		frappe.call({
			method: "account_party_bridge.utils.meta.rebuild_tree",
			args: {
				doctype: frm.doc.group_doctype,
				parent_field: frm.doc.group_parent_field,
			},
			freeze: true,
			freeze_message: __("Rebuilding..."),
			callback() {
				frappe.show_alert({ message: __("Tree rebuilt"), indicator: "green" });
			},
		});
	},
});

// ------------------------------------------------------------
frappe.ui.form.on("Account Party Field Map", {
	target_field(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.target_field || !frm.doc.party_doctype) return;

		get_fields(frm.doc.party_doctype).then((fields) => {
			const df = fields.find((d) => d.fieldname === row.target_field);
			if (df && df.reqd && !row.mandatory) {
				frappe.model.set_value(cdt, cdn, "mandatory", 1);
			}
		});
	},
});

// ------------------------------------------------------------
// helpers
// ------------------------------------------------------------
const _field_cache = {};

function get_fields(doctype) {
	if (_field_cache[doctype]) {
		return Promise.resolve(_field_cache[doctype]);
	}

	return frappe
		.call({
			method: "account_party_bridge.utils.meta.get_field_options",
			args: { doctype },
		})
		.then((r) => {
			_field_cache[doctype] = r.message || [];
			return _field_cache[doctype];
		});
}

function to_select_options(fields) {
	const options = [{ value: "", label: "" }];

	fields.forEach((d) => {
		const star = d.is_custom ? " *" : "";
		options.push({
			value: d.fieldname,
			label: `${d.label} (${d.fieldname}) [${d.fieldtype}]${star}`,
		});
	});

	return options;
}

function set_grid_options(frm, fieldname, options) {
	const grid = frm.fields_dict.field_mappings && frm.fields_dict.field_mappings.grid;
	if (!grid) return;

	grid.update_docfield_property(fieldname, "options", options);
	frm.refresh_field("field_mappings");
}
