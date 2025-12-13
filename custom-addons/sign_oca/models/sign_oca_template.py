# Copyright 2023 Dixmit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import base64

_logger = logging.getLogger(__name__)


class SignOcaTemplate(models.Model):
    _name = "sign.oca.template"
    _description = "Sign Oca Template"  # TODO
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    data = fields.Binary(attachment=True, required=True)
    ask_location = fields.Boolean()
    filename = fields.Char()
    item_ids = fields.One2many("sign.oca.template.item", inverse_name="template_id")
    request_count = fields.Integer(compute="_compute_request_count")
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        domain=[("transient", "=", False), ("model", "not like", "sign.oca")],
    )
    model = fields.Char(
        compute="_compute_model", string="Model name", compute_sudo=True, store=True
    )
    active = fields.Boolean(default=True)
    request_ids = fields.One2many("sign.oca.request", inverse_name="template_id")

    contract_type_id = fields.Many2one(
        'hr.contract.type',
        string='Loại Hợp Đồng',
        help='Chọn loại hợp đồng từ danh sách'
    )


    primary_attachment = fields.Binary(
        string='Tài Liệu Ủy Quyền',
        attachment=True,
        help='Tài liệu ủy quyền (1 file > 8MB)'
    )
    primary_attachment_filename = fields.Char(
        
    )
    @api.constrains('primary_attachment')
    def _check_file_size(self):
        for record in self:
            if record.primary_attachment:
                file_size = len(base64.b64decode(record.primary_attachment))
                max_size = 8 * 1024 * 1024  
                if file_size > max_size:
                    raise ValidationError(
                        'Kích Thước File Tài Liệu Ủy Quyền Vượt Quá 8MB. '
                        f'Kích Thước File: {file_size / (1024*1024):.2f}MB'
                        
                    )

    @api.depends("model_id")
    def _compute_model(self):
        for item in self:
            item.model = item.model_id.model or False

    @api.depends("request_ids")
    def _compute_request_count(self):
        res = self.env["sign.oca.request"].read_group(
            domain=[("template_id", "in", self.ids)],
            fields=["template_id"],
            groupby=["template_id"],
        )
        res_dict = {x["template_id"][0]: x["template_id_count"] for x in res}
        for record in self:
            record.request_count = res_dict.get(record.id, 0)

    def configure(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "sign_oca_configure",
            "name": self.name,
            "params": {
                "res_model": self._name,
                "res_id": self.id,
            },
        }

    def get_info(self):
        self.ensure_one()
        return {
            "name": self.name,
            "items": {item.id: item.get_info() for item in self.item_ids},
            "roles": [
                {"id": role.id, "name": role.name}
                for role in self.env["sign.oca.role"].search([])
            ],
            "fields": [
                {"id": field.id, "name": field.name}
                for field in self.env["sign.oca.field"].search([])
            ],
        }

    def delete_item(self, item_id):
        self.ensure_one()
        item = self.item_ids.browse(item_id)
        assert item.template_id == self
        item.unlink()

    def set_item_data(self, item_id, vals):
        self.ensure_one()
        item = self.env["sign.oca.template.item"].browse(item_id)
        assert item.template_id == self
        item.write(vals)

    def add_item(self, item_vals):
        self.ensure_one()
        item_vals["template_id"] = self.id
        return self.env["sign.oca.template.item"].create(item_vals).get_info()

    def _get_signatory_data(self, record=None):
        """Get signatory data with role-aware auto fill support"""
        items = sorted(
            self.item_ids,
            key=lambda item: (item.page, item.position_y, item.position_x),
        )
        
        signatory_data = {}
        tabindex = 1
        item_id = 1
        
        # Pre-fetch all auto-fill fields if record provided
        auto_fill_cache = {}
        if record:
            auto_fill_fields = [item for item in items if item.field_id.field_type == 'auto_fill']
            if auto_fill_fields:
                _logger.info(f"Processing {len(auto_fill_fields)} auto-fill fields for record {record._name}({record.id})")
                for item in auto_fill_fields:
                    try:
                        # 🔥 NEW: Prepare role context
                        role_context = {
                            'role_id': item.role_id.id if item.role_id else None,
                            'role_name': item.role_id.name if item.role_id else None,
                        }
                        
                        # Extract with role context
                        value = item.field_id.extract_value_from_record(record, role_context)
                        auto_fill_cache[item.field_id.id] = value
                        
                        if value:
                            role_info = f" (role: {role_context['role_name']})" if role_context['role_id'] else " (no role)"
                            _logger.info(f"Auto-filled field '{item.field_id.name}'{role_info} with value: '{value}'")
                    except Exception as e:
                        _logger.error(f"Failed to auto-fill field '{item.field_id.name}': {e}")
                        auto_fill_cache[item.field_id.id] = ""
        
        # Build signatory data with auto-fill values (rest remains same)
        for item in items:
            item_data = item.get_base_info()
            item_data.update({
                "id": item_id,
                "tabindex": tabindex,
                "field_type": item.field_id.field_type,
                "default_value": item.field_id.default_value,
            })
            
            # Set value based on field type
            if item.field_id.field_type == 'auto_fill' and record:
                item_data["value"] = auto_fill_cache.get(item.field_id.id, "")
                item_data["hr_field_selection"] = item.field_id.hr_field_selection
            else:
                item_data["value"] = False
            
            signatory_data[item_id] = item_data
            tabindex += 1
            item_id += 1
        
        return signatory_data

    def _prepare_sign_oca_request_vals_from_record(self, record):
        """Prepare request values with auto-fill data populated"""
        roles = self.mapped("item_ids.role_id").filtered(
            lambda x: x.partner_selection_policy != "empty"
        )
        
        # Get signatory data with auto-fill populated
        signatory_data = self._get_signatory_data(record)
        
        
        return {
            "name": self.name,
            "template_id": self.id,
            "record_ref": f"{record._name},{record.id}",
            "signatory_data": signatory_data,
            "data": self.data,
            "signer_ids": [
                (
                    0,
                    0,
                    {
                        "partner_id": role._get_partner_from_record(record),
                        "role_id": role.id,
                    },
                )
                for role in roles
            ],
        }

    def debug_auto_fill(self, record):
        """Debug method để kiểm tra auto fill functionality"""
        _logger.info(f"=== DEBUG AUTO FILL ===")
        _logger.info(f"Template: {self.name}")
        _logger.info(f"Record: {record._name} - {record.id}")
        
        # Check template items - sử dụng filtered() trên recordset thay vì list
        auto_fill_items = self.item_ids.filtered(lambda x: x.field_id.field_type == 'auto_fill')
        _logger.info(f"Auto fill items found: {len(auto_fill_items)}")
        
        for item in auto_fill_items:
            field_obj = item.field_id
            _logger.info(f"Field: {field_obj.name}")
            _logger.info(f"HR Selection: {field_obj.hr_field_selection}")
            
            # Test extraction
            try:
                value = field_obj.extract_value_from_record(record)
                _logger.info(f"Extracted value: '{value}'")
            except Exception as e:
                _logger.error(f"Extract error: {e}")
        
        # Check signatory data
        signatory_data = self._get_signatory_data(record)
        auto_fill_data = {k: v for k, v in signatory_data.items() 
                        if v.get('field_type') == 'auto_fill'}
        _logger.info(f"Auto fill in signatory_data: {len(auto_fill_data)} items")
        for k, v in auto_fill_data.items():
            _logger.info(f"  Item {k}: {v.get('name')} = '{v.get('value')}'")
        
        return signatory_data


class SignOcaTemplateItem(models.Model):
    _name = "sign.oca.template.item"
    _description = "Sign Oca Template Item"

    template_id = fields.Many2one(
        "sign.oca.template", required=True, ondelete="cascade"
    )
    field_id = fields.Many2one("sign.oca.field", ondelete="restrict")
    role_id = fields.Many2one(
        "sign.oca.role", default=lambda r: r._get_default_role(), ondelete="restrict"
    )
    required = fields.Boolean()
    # If no role, it will be editable by everyone...
    page = fields.Integer(required=True, default=1)
    position_x = fields.Float(required=True)
    position_y = fields.Float(required=True)
    width = fields.Float()
    height = fields.Float()
    placeholder = fields.Char()

    @api.model
    def _get_default_role(self):
        return self.env.ref("sign_oca.sign_role_customer")

    def get_info(self):
        """Legacy method - kept for compatibility"""
        return self.get_base_info()

    def get_base_info(self):
        """Get basic item information"""
        self.ensure_one()
        return {
            "id": self.id,
            "field_id": self.field_id.id,
            "name": self.field_id.name,
            "role_id": self.role_id.id,
            "page": self.page,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "width": self.width,
            "height": self.height,
            "placeholder": self.placeholder,
            "required": self.required,
        }