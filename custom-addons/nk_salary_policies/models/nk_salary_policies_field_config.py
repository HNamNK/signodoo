from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo import SUPERUSER_ID

class NkSalaryPoliciesFieldConfig(models.Model):
    _name = "nk.salary.policies.field.config"
    _description = "Cấu hình Trường Chính sách Lương"
    _order = "create_date desc, id"

    display_name = fields.Char("Tên hiển thị", required=True)
    excel_name = fields.Char("Tên cột Excel", required=True,
                             help="Không được chứa dấu cách. Người dùng KHÔNG nhập tiền tố 'x_'.")
    _sql_constraints = [
        ('unique_excel_name_global',
         'UNIQUE(excel_name)',
         'Tên Excel này đã tồn tại trong hệ thống! Vui lòng chọn tên khác.'),
    ]
    technical_name = fields.Char("Tên kỹ thuật", compute="_compute_technical_name", store=True, readonly=True)
    field_type = fields.Selection([
        ('char', "Văn bản"),
        ('float', "Số thập phân"),
        ('integer', "Số nguyên"),
        ('date', "Ngày"),
        ('boolean', 'Đúng/Sai'),
    ], string="Loại dữ liệu", required=True, default="float")

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

    @api.depends('excel_name')
    def _compute_technical_name(self):
        for r in self:
            r.technical_name = f"x_{r.excel_name.strip()}" if r.excel_name else False

    @api.model_create_multi
    def create(self, vals_list):
        if not self._is_admin():
            raise UserError(_("Chỉ Administrator mới được tạo cấu hình field."))
        rec = super().create(vals_list)
        rec.materialize_physical_field()
        return rec

    def write(self, vals):
        res = super().write(vals)
        if 'display_name' in vals:
            model = self.env['ir.model'].search([('model', '=', 'nk.salary.policies')], limit=1)
            IrFields = self.env['ir.model.fields']
            
            for rec in self.filtered('is_materialized'):
                field = IrFields.search([
                    ('model_id', '=', model.id),
                    ('name', '=', rec.technical_name)
                ], limit=1)
                
                if field and field.field_description != rec.display_name:
                    field.write({'field_description': rec.display_name})

        if self._is_admin() or self.env.context.get('materialize_now'):
            self.filtered(lambda r: not r.is_materialized).materialize_physical_field()
        
        return res

    def unlink(self):
        
        IrModelFields = self.env['ir.model.fields']
        
        for rec in self:
            if rec.is_materialized and rec.technical_name:
                has_data = self.env['nk.salary.policies'].search_count([
                    (rec.technical_name, '!=', False),
                    (rec.technical_name, '!=', 0),
                ])
                
                if has_data > 0:
                    raise UserError(
                        f"⚠️ Cảnh báo!\n\n"
                        f"Field '{rec.display_name}' đang có {has_data} bản ghi sử dụng.\n\n"
                        f"Xóa field sẽ MẤT TOÀN BỘ {has_data} giá trị này!\n\n"
                        f"Bạn có chắc chắn muốn xóa?"
                    )
                else:
                    pass

                model = self.env['ir.model'].search([('model', '=', 'nk.salary.policies')], limit=1)
                if model:
                    IrModelFields.search([
                        ('model_id', '=', model.id),
                        ('name', '=', rec.technical_name),
                        ('state', '=', 'manual'),
                    ]).unlink()

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
            field_name = rec.technical_name
            if not field_name:
                continue

            self._ensure_field_exists(model_policies, field_name, ttype, rec.display_name)
            rec.is_materialized = True

        self._refresh_registry()

        return True

    def _refresh_registry(self):
        
        try:
            self.env.registry.clear_caches()
            self.env.registry.setup_models(self.env.cr)
            self._cr.commit()

        except Exception as e:
            passs


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
