from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class NkSalaryPolicies(models.Model):
    _name = "nk.salary.policies"
    _description = "Employee Salary Policies"
    _rec_name = "employee_id"
    _order = "id desc"
    _check_company_auto = True
    
    
    batch_ref_id = fields.Many2one(
        "nk.salary.policies.batch",
        string="Import Batch",
        required=True,
        ondelete="cascade",
        index=True,
    )
    
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        ondelete="cascade",
        check_company=True,
        index=True,
    )
    
    employee_name = fields.Char(
        related="employee_id.name",
        string="Họ Tên NLĐ",
        store=True,
        readonly=True,
    )
    
    employee_identification = fields.Char(
        related="employee_id.identification",
        string="Số CCCD",
        store=True,
        readonly=True,
    )
    
    NLD_CCCD = fields.Char(
        string="NLD_CCCD",
        required=True,
        index=True,
    )
    
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('in_use', 'Đang áp dụng'),
        ('used', 'Đã áp dụng'),
    ], string='Trạng thái', 
       default='draft',
       required=True,
       index=True,
       readonly=True)
    
    activated_date = fields.Datetime(
        string="Ngày Kích Hoạt",
        readonly=True,
        help="Ngày chính sách lương được chuyển sang trạng thái 'Đang áp dụng'",
        index=True,
    )


    
    _sql_constraints = [
        ('unique_employee_batch', 
         'UNIQUE(employee_id, batch_ref_id)',
         'Nhân viên không được trùng trong cùng batch!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            
            if not vals.get("state"):
                vals["state"] = "draft"
            
            if not vals.get("employee_id") and vals.get("NLD_CCCD"):
                cccd = str(vals["NLD_CCCD"]).strip()
                employee = self.env["hr.employee"].search(
                    [("identification", "=", cccd),
                    ("company_id", "=", vals["company_id"])],
                    limit=1,
                )
                if employee:
                    vals["employee_id"] = employee.id
                else:
                    raise UserError(
                        _("Không tìm thấy nhân viên có CCCD '%s' trong công ty hiện tại") % cccd
                    )
        return super().create(vals_list)

    
    def unlink(self):
        for rec in self:
            if rec.batch_ref_id.state in ('in_use', 'used'):
                raise UserError(_("Không thể xóa policies của batch đã áp dụng!"))
        return super().unlink()

    def write(self, vals):
        
        LogModel = self.env['nk.salary.policies.log']
        
        for rec in self:
            old_values = {}
            if vals.get('state') == 'in_use' and rec.state != 'in_use':
                        if not rec.activated_date:  # Chỉ set 1 lần duy nhất
                            vals['activated_date'] = fields.Datetime.now()
                            _logger.info(f"📅 Set activated_date for policy {rec.id} of employee {rec.employee_id.name}")

            for field_name in vals.keys():
                if field_name in ['write_date', 'write_uid', '__last_update']:
                    continue
                
                field = self._fields.get(field_name)
                if not field:
                    continue
                
                old_val = rec[field_name]
                
                if field.type == 'many2one':
                    old_values[field_name] = old_val.display_name if old_val else ''
                elif field.type in ('selection', 'boolean', 'integer', 'float', 'monetary'):

                    old_values[field_name] = self._clean_number_str(old_val) if old_val else ''
                else:
                    old_values[field_name] = old_val or ''
            
            result = super(NkSalaryPolicies, rec).write(vals)
            
            for field_name, old_val in old_values.items():
                new_val = rec[field_name]
                
                field = self._fields.get(field_name)
                
                if field.type == 'many2one':
                    new_val_str = new_val.display_name if new_val else ''
                elif field.type in ('selection', 'boolean', 'integer', 'float', 'monetary'):

                    new_val_str = self._clean_number_str(new_val) if new_val else ''
                else:
                    new_val_str = new_val or ''
                
                old_val_str = str(old_val) if old_val else ''
                
                if old_val_str == new_val_str:
                    continue
                

                if field_name == 'state':
                    action_type = 'policies_state_change'
                    state_labels = dict(self._fields['state'].selection)
                    old_display = state_labels.get(old_val_str, old_val_str)
                    new_display = state_labels.get(new_val_str, new_val_str)
                    description = f"Trạng thái thay đổi: {old_display or '(trống)'} → {new_display or '(trống)'}"
                else:
                    action_type = 'policies_field_change'
                    old_display = old_val_str
                    new_display = new_val_str
                    if field_name.startswith('x_'):
                        configs = self.env["nk.salary.policies.field.config"].get_effective_fields(
                            company=rec.company_id,
                            user=self.env.user
                        )
                        config = next((c for c in configs if c.technical_name == field_name), None)
                        field_label = config.display_name if config else field.string or field_name
                    else:
                        field_label = field.string or field_name
                    description = f"Trường '{field_label}' thay đổi: {old_display or '(trống)'} → {new_display or '(trống)'}"
                
                LogModel.create({
                    'batch_id': rec.batch_ref_id.id,
                    'policies_ids': rec.id,
                    'company_id': rec.company_id.id,
                    'employee_id': rec.employee_id.id,
                    'log_level': 'record',
                    'action_type': action_type,
                    'field_name': field_name,
                    'old_value': old_display,
                    'new_value': new_display,
                    'description': description,
                })
        
        return True

    def _clean_number_str(self, value):
        
        if value is False or value is None:
            return ''
        
        str_val = str(value)
        

        if str_val.endswith('.0'):
            return str_val[:-2]
        
        return str_val    
   
   
    @api.model
    def load(self, import_fields, data):
        """
        Override load để validate và xử lý import từ Excel
        """
        # ========================================
        # VALIDATE BATCH
        # ========================================
        batch_id = self.env.context.get('default_batch_ref_id')
        if not batch_id:
            raise UserError(_("Vui lòng import từ Batch Form!"))
        
        batch = self.env['nk.salary.policies.batch'].browse(batch_id)
        if not batch.exists():
            raise UserError(_("Batch không tồn tại!"))
        
        if batch.total_records > 0:
            raise UserError(
                _("Batch này đã có %d records!\n"
                "Không cho phép import thêm.\n"
                "Vui lòng tạo batch mới.") % batch.total_records
            )
        
        if batch.state != 'draft':
            raise UserError(_("Chỉ có thể import vào batch ở trạng thái Nháp!"))
        
        # ========================================
        # LẤY CONFIGS VÀ MATERIALIZE
        # ========================================
        configs = self.env["nk.salary.policies.field.config"].get_effective_fields(
            company=batch.company_id,
            user=self.env.user
        )
        
        non_materialized = configs.filtered(lambda c: not c.is_materialized)
        if non_materialized:
            _logger.info(f"🔧 Materializing {len(non_materialized)} fields trước khi import...")
            non_materialized.sudo().materialize_physical_field()
        
        # ========================================
        # MAP EXCEL NAME → TECHNICAL NAME
        # ========================================
        mapping = {}
        for c in configs:
            if c.excel_name and c.technical_name:
                mapping[c.excel_name] = c.technical_name
        
        SYSTEM_FIELDS = [
            "NLD_CCCD", 
            "employee_id", 
            "employee_name",
            "employee_identification", 
            "company_id", 
            "state",
            "batch_ref_id"
        ]
        
        # ========================================
        # VALIDATE INVALID COLUMNS
        # ========================================
        invalid = []
        for f in import_fields:
            if f in SYSTEM_FIELDS or f.startswith('x_'):
                continue
            if f not in mapping:
                invalid.append(f)
        
        if invalid:
            raise UserError(
                _("❌ Cột không hợp lệ: %s\n\n"
                "💡 Gợi ý: Hãy đảm bảo tên cột Excel khớp với 'Tên cột Excel' "
                "trong cấu hình field config.") % ", ".join(invalid)
            )
        
        # ========================================
        # CONVERT FIELDS
        # ========================================
        new_fields = []
        for f in import_fields:
            if f in mapping:
                new_fields.append(mapping[f])
            else:
                new_fields.append(f)
        
        # ========================================
        # SYNC FIELD DESCRIPTIONS
        # ========================================
        model = self.env['ir.model'].search([('model', '=', 'nk.salary.policies')], limit=1)        
        IrFields = self.env['ir.model.fields'].sudo()
        
        for cfg in configs:
            if cfg.technical_name and cfg.technical_name.startswith('x_'):
                field = IrFields.search([
                    ('model_id', '=', model.id),
                    ('name', '=', cfg.technical_name)
                ], limit=1)
                
                if field:
                    if field.field_description != cfg.display_name:
                        field.write({'field_description': cfg.display_name})
                        _logger.info(f"✅ Synced field_description: {cfg.technical_name} → '{cfg.display_name}'")
        
        # ========================================
        # VALIDATE CCCD
        # ========================================
        try:
            cccd_idx = new_fields.index("NLD_CCCD")
        except ValueError:
            raise UserError(_("❌ Thiếu cột NLD_CCCD!\n\n"
                            "Cột này là bắt buộc để map nhân viên."))
        
        errors = []
        cccd_cache = {}
        
        for i, row in enumerate(data, 1):
            cccd = str(row[cccd_idx]).strip() if row[cccd_idx] else False
            
            if not cccd:
                errors.append(f"Dòng {i}: Thiếu CCCD")
                continue
            
            if cccd not in cccd_cache:
                emp = self.env["hr.employee"].search([
                    ("identification", "=", cccd),
                    ("company_id", "=", batch.company_id.id)
                ], limit=1)
                cccd_cache[cccd] = emp
            
            if not cccd_cache[cccd]:
                errors.append(f"Dòng {i}: Không tìm thấy NV có CCCD '{cccd}'")
        
        if errors:
            error_msg = "\n".join(errors[:20])
            if len(errors) > 20:
                error_msg += f"\n\n... và {len(errors) - 20} lỗi khác"
            
            raise UserError(_("❌ Lỗi validation:\n\n%s") % error_msg)
        
        # ========================================
        # CLEAN DATA
        # ========================================
        cleaned_data = []
        for row in data:
            cleaned_row = []
            for cell in row:
                if cell == '' or cell is None:
                    cleaned_row.append(None)
                elif isinstance(cell, str):
                    stripped = cell.strip()
                    cleaned_row.append(stripped if stripped else None)
                else:
                    cleaned_row.append(cell)
            cleaned_data.append(cleaned_row)
        
        # ========================================
        # VALIDATE REQUIRED FIELDS
        # ========================================
        required_configs = configs.filtered(lambda c: c.required_on_import and c.technical_name)
        
        if required_configs:
            required_errors = []
            
            # Map technical_name -> index trong new_fields
            required_indices = {}
            for cfg in required_configs:
                try:
                    idx = new_fields.index(cfg.technical_name)
                    required_indices[cfg.technical_name] = (idx, cfg.display_name)
                except ValueError:
                    # Field không có trong import -> bỏ qua (user không import field này)
                    pass
            
            # Validate từng row
            for i, row in enumerate(cleaned_data, 1):
                for tech_name, (idx, display_name) in required_indices.items():
                    cell_value = row[idx] if idx < len(row) else None
                    
                    # Check empty
                    if cell_value is None or cell_value == '' or str(cell_value).strip() == '':
                        required_errors.append(
                            f"Dòng {i}: Field '{display_name}' không được để trống"
                        )
            
            if required_errors:
                error_msg = "\n".join(required_errors[:30])
                if len(required_errors) > 30:
                    error_msg += f"\n\n... và {len(required_errors) - 30} lỗi khác"
                
                raise UserError(_("❌ Lỗi validation field bắt buộc:\n\n%s") % error_msg)
        
        # ========================================
        # PROCEED WITH IMPORT
        # ========================================
        _logger.info(f"📥 Importing {len(cleaned_data)} rows with fields: {new_fields}")
        
        result = super().load(new_fields, cleaned_data)
        
        # ========================================
        # POST-IMPORT PROCESSING
        # ========================================
        created_ids = result.get("ids", [])
        if not created_ids:
            _logger.warning("⚠️ Import không tạo được record nào")
            return result
        
        _logger.info(f"✅ Imported {len(created_ids)} records successfully")
        
        # Gán batch_ref_id và state
        self.browse(created_ids).write({
            'batch_ref_id': batch.id,
            'state': 'draft'
        })
        
        # Lưu danh sách dynamic fields
        imported_fields = [f for f in new_fields if f.startswith("x_")]
        
        if imported_fields:
            batch.write({'dynamic_field_names': ",".join(imported_fields)})
        
        # Generate dynamic list view
        is_module_install = (
            self.env.context.get('_import_current_module') or
            self.env.context.get('install_mode')
        )
        
        if not is_module_install and imported_fields:
            _logger.info(f"🎨 Generating dynamic list view with {len(imported_fields)} fields...")
            batch._generate_dynamic_list_view(imported_fields, configs)
        else:
            if is_module_install:
                _logger.info("⏭️ Skipping view generation (module install mode)")
            else:
                _logger.warning("⚠️ No dynamic fields to generate view")
        
        # Tạo log
        batch._create_log(
            action_type='batch_import',
            description=f"Import thành công {len(created_ids)} nhân viên - {len(imported_fields)} trường dữ liệu",
        )
        
        return result