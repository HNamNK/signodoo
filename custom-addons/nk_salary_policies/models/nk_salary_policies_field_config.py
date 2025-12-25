from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo import SUPERUSER_ID
import unicodedata
import re
from markupsafe import Markup

class NkSalaryPoliciesFieldConfig(models.Model):
    _name = "nk.salary.policies.field.config"
    _description = "Cấu hình Trường Chính sách Lương"
    _order = "create_date desc, id"
    _rec_name = "excel_name"
    _inherit = ['mail.thread']

    excel_name = fields.Char("Tên cột Excel", required=True,
                             help="Không được chứa dấu cách. Người dùng KHÔNG nhập tiền tố 'x_'.")
    _sql_constraints = [
        ('unique_technical_name_global',
        'UNIQUE(technical_name)',
        'Technical name đã tồn tại! Excel name khác nhau có thể tạo ra cùng technical name khi bỏ dấu.\n'
        'Ví dụ: "Phụ Cấp" và "Phụ-Cấp" đều tạo ra "x_phu_cap".\n'
        'Vui lòng đặt tên Excel khác để tránh trùng lặp.'),
    ]
    technical_name = fields.Char("Tên kỹ thuật", compute="_compute_technical_name", store=True, readonly=True)
    field_type = fields.Selection([
        ('char', "Văn bản"),
        ('float', "Số thập phân"),
        ('integer', "Số nguyên"),
        ('date', "Ngày"),
        ('boolean', 'Đúng/Sai'),
    ], string="Loại dữ liệu", required=True, default="float" )

    company_ids = fields.Many2many(
        "res.company", 
        "nk_salary_field_config_company_rel", 
        "config_id", 
        "company_id",
        string="Công ty sở hữu",
        help="Để trống = global (dùng chung toàn hệ thống). Chọn nhiều công ty = field này dùng cho các công ty đó."
    )

    is_materialized = fields.Boolean(string="Đã vật lý hóa", default=False,
                                     help="True nếu đã tạo ir.model.fields cho config này.")

    scope_display = fields.Selection([('global','Dùng chung toàn hệ thống'), ('company','Công ty riêng')],
                                     compute="_compute_scope_display", store=False, string="Phạm vi")


    required_on_import = fields.Boolean(
        string="Bắt buộc khi import",
        default=False,
        help="Nếu bật, field này không được để trống khi import Excel"
    )


    
    def _is_admin(self):
        """Kiểm tra user có quyền Administrator không"""
        return self.env.user.has_group('base.group_system')


    @api.depends('company_ids')
    def _compute_scope_display(self):
        for r in self:
            r.scope_display = 'global' if not r.company_ids else 'company'


    @api.onchange('excel_name')
    def _onchange_excel_name(self):
        """Tính technical_name ngay khi user gõ xong excel_name"""
        if self.excel_name:
            try:
                normalized = self._normalize_to_technical_name(self.excel_name.strip())
                self.technical_name = f"x_{normalized}"
                
                # Kiểm tra trùng technical_name (nếu đang tạo mới)
                if not self.id:
                    existing = self.search([('technical_name', '=', self.technical_name)], limit=1)
                    if existing:
                        return {
                            'warning': {
                                'title': 'Cảnh báo trùng lặp!',
                                'message': f'Technical name "{self.technical_name}" đã tồn tại!\n'
                                        f'Excel name "{self.excel_name}" tạo ra technical name trùng với field "{existing.excel_name}".\n'
                                        f'Vui lòng đặt tên Excel khác.'
                            }
                        }
            except UserError as e:
                # Nếu excel_name không hợp lệ, để technical_name trống
                self.technical_name = False
                return {
                    'warning': {
                        'title': 'Tên không hợp lệ!',
                        'message': str(e)
                    }
                }
        else:
            self.technical_name = False

    @api.depends('excel_name')
    def _compute_technical_name(self):
        for r in self:
            if r.excel_name:
                try:
                    normalized = r._normalize_to_technical_name(r.excel_name.strip())
                    r.technical_name = f"x_{normalized}"
                except UserError:
                    # Re-raise để hiển thị lỗi cho user
                    raise
            else:
                r.technical_name = False
    def _normalize_to_technical_name(self, text):

        if not text:
            return ''

        vietnamese_map = {
            'Đ': 'D', 'đ': 'd',
            
            'À': 'A', 'Á': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
            'Ă': 'A', 'Ằ': 'A', 'Ắ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
            'Â': 'A', 'Ầ': 'A', 'Ấ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
            
            'È': 'E', 'É': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
            'Ê': 'E', 'Ề': 'E', 'Ế': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
            
            'Ì': 'I', 'Í': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
            
            'Ò': 'O', 'Ó': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
            'Ô': 'O', 'Ồ': 'O', 'Ố': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
            'Ơ': 'O', 'Ờ': 'O', 'Ớ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
            
            'Ù': 'U', 'Ú': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
            'Ư': 'U', 'Ừ': 'U', 'Ứ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
            
            'Ỳ': 'Y', 'Ý': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y',
            
            'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
            'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
            'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
            
            'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
            'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
            
            'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
            
            'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
            'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
            'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
            
            'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
            'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
            
            'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
        }
        
        for vn_char, latin_char in vietnamese_map.items():
            text = text.replace(vn_char, latin_char)
        
        text = text.lower()
        
        nfd = unicodedata.normalize('NFD', text)
        without_accents = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
        
        normalized = re.sub(r'[^a-z0-9]+', '_', without_accents)
        
        normalized = normalized.strip('_')
        normalized = re.sub(r'_+', '_', normalized)  
        if not normalized:
            raise UserError(_(
                "Excel name '%s' không hợp lệ!\n"
                "Sau khi bỏ dấu và ký tự đặc biệt không còn ký tự nào."
            ) % text)
        
        return normalized


    @api.model_create_multi
    def create(self, vals_list):
        if not self._is_admin():
            raise UserError(_("Chỉ Administrator mới được tạo cấu hình field."))
        
        rec = super().create(vals_list)
        rec.materialize_physical_field()
        
        for r in rec:
            scope = 'Dùng chung toàn hệ thống' if not r.company_ids else ', '.join(r.company_ids.mapped("name"))
            
            # ✅ Dùng Markup
            message = Markup(f"""
                <p><strong>✅ Tạo thành công field: {r.excel_name}</strong></p>
                <p>• Tên kỹ thuật: <code>{r.technical_name}</code><br/>
                • Loại dữ liệu: {dict(r._fields['field_type'].selection).get(r.field_type)}<br/>
                • Phạm vi: {scope}<br/>
                • Bắt buộc import: {'Có' if r.required_on_import else 'Không'}</p>
            """)
            
            r.message_post(
                body=message,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        
        return rec

    def write(self, vals):
        # ✅ Lưu giá trị cũ để so sánh
        old_values = {}
        for rec in self:
            old_values[rec.id] = {
                'excel_name': rec.excel_name,
                'field_type': rec.field_type,
                'company_ids': rec.company_ids.ids,
                'required_on_import': rec.required_on_import,
            }
        
        res = super().write(vals)
        
        if 'excel_name' in vals:  
            model = self.env['ir.model'].search([('model', '=', 'nk.salary.policies')], limit=1)
            IrFields = self.env['ir.model.fields']
            
            for rec in self.filtered('is_materialized'):
                field = IrFields.search([
                    ('model_id', '=', model.id),
                    ('name', '=', rec.technical_name)
                ], limit=1)
                
                if field and field.field_description != rec.excel_name:  
                    field.write({'field_description': rec.excel_name})  

        if self._is_admin() or self.env.context.get('materialize_now'):
            self.filtered(lambda r: not r.is_materialized).materialize_physical_field()
        
        # ✅ Ghi log note khi cập nhật
        for rec in self:
            old = old_values.get(rec.id, {})
            changes = []
            
            if 'excel_name' in vals and old.get('excel_name') != rec.excel_name:
                changes.append(f"Tên hiển thị: {old.get('excel_name')} → {rec.excel_name}")
            
            if 'field_type' in vals and old.get('field_type') != rec.field_type:
                old_type = dict(rec._fields['field_type'].selection).get(old.get('field_type'))
                new_type = dict(rec._fields['field_type'].selection).get(rec.field_type)
                changes.append(f"Loại dữ liệu: {old_type} → {new_type}")
            
            if 'company_ids' in vals:
                old_scope = 'Dùng chung toàn hệ thống' if not old.get('company_ids') else 'Theo công ty'
                new_scope = 'Dùng chung toàn hệ thống' if not rec.company_ids else ', '.join(rec.company_ids.mapped("name"))
                if old_scope != new_scope:
                    changes.append(f"Phạm vi: {old_scope} → {new_scope}")
            
            if 'required_on_import' in vals and old.get('required_on_import') != rec.required_on_import:
                old_req = 'Có' if old.get('required_on_import') else 'Không'
                new_req = 'Có' if rec.required_on_import else 'Không'
                changes.append(f"Bắt buộc import: {old_req} → {new_req}")
            
            # ✅ Nếu có thay đổi thì ghi log
            if changes:
                from markupsafe import Markup
                message = Markup(f"""
                    <p><strong>🔄 Cập nhật field: {rec.excel_name}</strong></p>
                    <p>• Tên kỹ thuật: <code>{rec.technical_name}</code><br/>
                    {'<br/>'.join(['• ' + change for change in changes])}</p>
                """)
                
                rec.message_post(
                    body=message,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
        
        return res

    def unlink(self):
        IrModelFields = self.env['ir.model.fields']
        IrUiView = self.env['ir.ui.view'].sudo()
        
        for rec in self:
            if rec.is_materialized and rec.technical_name:
                has_data = self.env['nk.salary.policies'].search_count([
                    (rec.technical_name, '!=', False),
                    (rec.technical_name, '!=', 0),
                ])
                
                if has_data > 0:
                    raise UserError(
                        f"⚠️ Cảnh báo!\n\n"
                        f"Field '{rec.excel_name}' đang có {has_data} bản ghi sử dụng.\n\n"
                        f"Xóa field sẽ MẤT TOÀN BỘ {has_data} giá trị này!\n\n"
                        f"Bạn có chắc chắn muốn xóa?"
                    )
                
                views_with_field = IrUiView.search([
                    ('model', '=', 'nk.salary.policies'),
                    ('type', '=', 'list'),
                    ('arch_db', 'ilike', f'field name="{rec.technical_name}"')
                ])
                
                if views_with_field:
                    batches = self.env['nk.salary.policies.batch'].search([
                        ('list_view_id', 'in', views_with_field.ids)
                    ])
                    
                    if batches:
                        batches.write({'list_view_id': False})
                    
                    views_with_field.unlink()
                
                model = self.env['ir.model'].search([('model', '=', 'nk.salary.policies')], limit=1)
                if model:
                    field_to_delete = IrModelFields.search([
                        ('model_id', '=', model.id),
                        ('name', '=', rec.technical_name),
                        ('state', '=', 'manual'),
                    ])
                    
                    if field_to_delete:
                        field_to_delete.unlink()

        res = super().unlink()
        
        self._refresh_registry()
        
        return res


    @api.model
    def get_effective_fields(self, company=None, user=None):

        user = self.env.user
        allowed_company_ids = user.company_ids.ids
        domain = ['|', ('company_ids', '=', False), ('company_ids', 'in', allowed_company_ids)]
        return self.search(domain)

    def materialize_physical_field(self):
        if not self._is_admin():
            raise UserError(_("Chỉ admin hệ thống mới được vật lý hóa field."))
        
        model_policies = self.env['ir.model'].search([
            ('model', '=', 'nk.salary.policies')
        ], limit=1)
        
        if not model_policies:
            raise UserError(_("Không tìm thấy model nk.salary.policies để tạo trường vật lý."))
        
        type_map = {
            'char': 'char',
            'float': 'float',
            'integer': 'integer',
            'date': 'date',
            'boolean': 'boolean',
        }
        
        for rec in self:
            ttype = type_map.get(rec.field_type)
            
            # ✅ SỬA: Dùng technical_name thay vì excel_name
            if not rec.technical_name:
                continue

            # ✅ SỬA: Truyền technical_name (có x_) vào field_name
            self._ensure_field_exists(
                model_policies, 
                rec.technical_name,  # ← Thay đổi từ rec.excel_name
                ttype, 
                rec.excel_name  # Label vẫn dùng excel_name
            )
            rec.is_materialized = True

        self._refresh_registry()
        return True

    def _refresh_registry(self):
        
        try:
            self.env.registry.clear_caches()
            self.env.registry.setup_models(self.env.cr)
            self._cr.commit()

        except Exception as e:
            pass


    def _ensure_field_exists(self, model, field_name, ttype, label):

        IrFields = self.env['ir.model.fields'].sudo()
        field = IrFields.search([
            ('model_id', '=', model.id), 
            ('name', '=', field_name)
        ], limit=1)
        
        if not field:
            field = IrFields.create({
                'name': field_name,
                'field_description': label,
                'model_id': model.id,
                'ttype': ttype,
                'state': 'manual',
            })

        else:
            if field.field_description != label:
                field.write({'field_description': label})

        if ttype in ('integer', 'float', 'monetary'):
            table_name = model.model.replace('.', '_')
            try:
                self.env.cr.execute(f'''
                    ALTER TABLE {table_name} 
                    ALTER COLUMN "{field_name}" DROP NOT NULL;
                ''')
                self.env.cr.execute(f'''
                    ALTER TABLE {table_name} 
                    ALTER COLUMN "{field_name}" DROP DEFAULT;
                ''')
            except Exception as e:
                pass
