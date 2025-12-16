from odoo import api, fields, models, _
from odoo.exceptions import UserError

class NkSalaryImportBatch(models.Model):
    _name = "nk.salary.policies.batch"
    _description = "Salary policies Batch"
    _order = "create_date desc"
    _check_company_auto = True
    
    name = fields.Char(
        "Tên Chính Sách Lương",
        required=True,
        index=True,
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    
    
    create_date = fields.Datetime(
        "Ngày tạo",
        readonly=True,
        index=True,
    )
    
    effective_date = fields.Date(
        "Ngày áp dụng",
        readonly=True,
    )
    
    expiration_date = fields.Date(
        "Ngày kết thúc",
        readonly=True,
    )
    
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('in_use', 'Đang sử dụng'),
        ('used', 'Đã sử dụng'),
    ], string='Trạng thái', 
       default='draft',
       required=True, 
       readonly=True,
       index=True)
    
    total_records = fields.Integer(
        "Tổng NV",
        compute="_compute_stats",
        store=True,
    )
    
    policies_ids = fields.One2many(
        "nk.salary.policies",
        "batch_ref_id",
        string="Policies",
    )
    
    dynamic_field_names = fields.Text(
        string="Dánh sách trường dữ liệu",
        readonly=True,
        copy=False,
    )
    
    list_view_id = fields.Many2one(
        'ir.ui.view',
        string='List View',
        readonly=True,
        ondelete='set null',  
        copy=False, 
    )

    log_ids = fields.One2many(
        'nk.salary.policies.log',
        'batch_id',
        string='Logs',
    )

    batch_log_count = fields.Integer(
        string='Số log Batch',
        compute='_compute_log_counts',
    )

    record_log_count = fields.Integer(
        string='Số log Record',
        compute='_compute_log_counts',
    )
    
    create_uid = fields.Many2one(
        'res.users',
        string='Người tạo',
        readonly=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create để prevent duplicate batch khi switch company"""
        from datetime import timedelta
        
        created_records = self.env['nk.salary.policies.batch']
        
        for vals in vals_list:

            if vals.get('name'):
                duplicate = self.search([
                    ('name', '=', vals['name']),
                    ('state', '=', 'draft'),
                    ('total_records', '=', 0),
                    ('create_date', '>=', fields.Datetime.now() - timedelta(seconds=3)),
                ], limit=1)
                
                if duplicate:

                    created_records |= duplicate
                    continue
            

            new_record = super(NkSalaryImportBatch, self).create([vals])
            created_records |= new_record
            

            new_record._create_log(
                action_type='batch_create',
                description=f"Tạo mới Bảng Chính Sách lương: {new_record.name}",
            )
        
        return created_records


    def open_policies_from_contract(self):
        
        self.ensure_one()
        
        employee_id = self.env.context.get('employee_filter_id')
        
        if employee_id:
            return self.with_context(employee_filter_id=employee_id).action_view_policies()
        else:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'nk.salary.policies.batch',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
            }

    @api.depends('log_ids')
    def _compute_log_counts(self):
        for batch in self:
            batch.batch_log_count = len(batch.log_ids.filtered(lambda l: l.log_level == 'batch'))
            batch.record_log_count = len(batch.log_ids.filtered(lambda l: l.log_level == 'record'))

    def _create_log(self, action_type, description, log_level='batch', policies_ids=None, employee_id=None, is_auto=False, trigger_batch_id=None):
        self.ensure_one()
        return self.env['nk.salary.policies.log'].create({
            'batch_id': self.id,
            'policies_ids': policies_ids,
            'company_id': self.company_id.id,
            'employee_id': employee_id,
            'log_level': log_level,
            'action_type': action_type,
            'description': description,
            'is_auto': is_auto,
            'trigger_batch_id': trigger_batch_id,
        })
    
    def action_view_logs(self):
        
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lịch sử - %s') % self.name,
            'res_model': 'nk.salary.policies.log',
            'view_mode': 'list', 
            'domain': [('batch_id', '=', self.id)],
            'context': {
                'default_batch_id': self.id,
                'default_company_id': self.company_id.id,
            },
            'target': 'current',
        }

    @api.depends("policies_ids")
    def _compute_stats(self):
        for batch in self:
            batch.total_records = len(batch.policies_ids)
    
    def action_import_records(self):
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_("Chỉ có thể import vào batch ở trạng thái Nháp!"))
        
        if self.total_records > 0:
            raise UserError(
                _("Batch này đã có %d records!\n"
                  "Không cho phép import thêm.\n"
                  "Vui lòng tạo batch mới.") % self.total_records
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'import',
            'params': {
                'model': 'nk.salary.policies',
                'context': {
                    'default_batch_ref_id': self.id,
                    'default_company_id': self.company_id.id,
                },
            }
        }
    
    def action_view_policies(self):
        self.ensure_one()
        

        if not self.list_view_id and self.dynamic_field_names:
            field_list = [f.strip() for f in self.dynamic_field_names.split(',') if f.strip()]
            if field_list:
                configs = self.env["nk.salary.policies.field.config"].get_effective_fields(
                    company=self.company_id,
                    user=self.env.user
                )
                self._generate_dynamic_list_view(field_list, configs)
        
        domain = [
            ('batch_ref_id', '=', self.id),
            ('company_id', '=', self.company_id.id)
        ]
        employee_id = self.env.context.get('employee_filter_id')
        if employee_id:
            domain.append(('employee_id', '=', employee_id))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _("Policies - %s") % self.name,
            'res_model': 'nk.salary.policies',
            'views': [
                (self.list_view_id.id if self.list_view_id else False, 'list'),
            ],
            'view_mode': 'list',
            'domain': domain,
            'context': {
                'default_batch_ref_id': self.id,
                'default_company_id': self.company_id.id,
            },
            'target': 'current',
        }
    
    def action_approve_batch(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Chỉ có thể áp dụng batch ở trạng thái Nháp!"))
            
            if rec.total_records == 0:
                raise UserError(_("Không thể áp dụng batch rỗng!\nVui lòng import dữ liệu trước."))
            current_policies = rec.policies_ids
            affected_batches = set()
            for policies in current_policies:
                employee = policies.employee_id
                old_policies = self.env['nk.salary.policies'].search([
                    ('employee_id', '=', employee.id),
                    ('company_id', '=', rec.company_id.id),
                    ('state', '=', 'in_use'),
                    ('batch_ref_id', '!=', rec.id),
                ])
                
                if old_policies:

                    old_policies.write({'state': 'used'})
                    for old_policies in old_policies:
                        old_policies.batch_ref_id._create_log(  
                            action_type='policies_state_change',
                            description=f"policies của NV {employee.name} tự động chuyển sang 'used' do Batch '{rec.name}' được áp dụng",
                            log_level='record',
                            policies_ids=old_policies.id,
                            employee_id=employee.id,
                            is_auto=True,
                            trigger_batch_id=rec.id,
                        )
                    affected_batches.update(old_policies.mapped('batch_ref_id').ids)
            rec.write({
                'state': 'in_use',
                'effective_date': fields.Date.today(),
            })
            current_policies.write({'state': 'in_use'})
            rec._create_log(
                action_type='batch_approve',
                description=f"Áp dụng Bảng Chính Sách lương: {rec.name} - {rec.total_records} nhân viên",
            )
            if affected_batches:
                self._auto_close_completed_batches(list(affected_batches))
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}    

    def _auto_close_completed_batches(self, batch_ids):

        batches_to_check = self.browse(batch_ids)
        
        for batch in batches_to_check:
            if batch.state != 'in_use':
                continue
            total_policies = len(batch.policies_ids)
            used_policies = len(batch.policies_ids.filtered(lambda p: p.state == 'used'))
            if total_policies > 0 and used_policies == total_policies:

                batch.write({
                    'state': 'used',
                    'expiration_date': fields.Date.today(),
                })
    
    def action_end_batch(self):

        for rec in self:
            if rec.state != 'in_use':
                raise UserError(_("Chỉ có thể kết thúc Bảng Chính Sách lương đang sử dụng!"))
            rec.policies_ids.filtered(lambda p: p.state == 'in_use').write({'state': 'used'})
            
            rec.write({
                'state': 'used',
                'expiration_date': fields.Date.today(),
            })
        rec._create_log(
            action_type='batch_end',
            description=f"Kết thúc batch: {rec.name}",
        )
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    
    def _generate_dynamic_list_view(self, field_list, configs):
        """
        Tạo dynamic list view.
        Header LUÔN dùng display_name từ config.
        """
        self.ensure_one()
        

        old_view = self.list_view_id
        if old_view:
            self.write({'list_view_id': False})
            old_view.sudo().unlink()
        
        config_map = {c.excel_name: c for c in configs if c.excel_name}
        
        IrModelFields = self.env['ir.model.fields'].sudo()
        model_id = self.env['ir.model'].sudo().search([
            ('model', '=', 'nk.salary.policies')
        ], limit=1)
        
        if not model_id:
            raise UserError(_("Model nk.salary.policies không tồn tại"))
        
        valid_fields = []
        for fname in field_list:
            field_exists = IrModelFields.search([
                ('model_id', '=', model_id.id),
                ('name', '=', fname)
            ], limit=1)
            
            if field_exists:
                valid_fields.append(fname)
                cfg = config_map.get(fname)
                if cfg and field_exists.field_description != cfg.display_name:
                    field_exists.write({'field_description': cfg.display_name})

            else:
                pass

        
        arch_lines = [
            '<?xml version="1.0"?>',
            '<list create="0" edit="1" delete="0" string="Policies" editable="top" class="nk_salary_policies_list">',
            '    <field name="employee_name" string="Họ Tên NLĐ"/>',
            '    <field name="employee_identification" string="Số CCCD"/>',
            '    <field name="state" string="Trạng thái" widget="badge" '
            '           decoration-info="state == \'draft\'" '
            '           decoration-success="state == \'in_use\'" '
            '           decoration-muted="state == \'used\'"/>',
        ]
        
        for fname in valid_fields:
            cfg = config_map.get(fname)
            
            if cfg:
                label = cfg.display_name
                field_type = cfg.field_type

            else:
                field_obj = IrModelFields.search([
                    ('model_id', '=', model_id.id),
                    ('name', '=', fname)
                ], limit=1)
                
                if field_obj:
                    label = field_obj.field_description
                    field_type = 'float' if field_obj.ttype in ('float', 'monetary') else 'char'

                else:

                    continue
            
            auto_width = max(100, len(label) * 8 + 40)
            
            if field_type in ('integer', 'float', 'monetary'):
                arch_lines.append(
                    f'    <field name="{fname}" '
                    f'string="{label}" '
                    f'widget="null_float" '
                    f'width="{auto_width}px" '
                    f'readonly="state != \'draft\'" '
                    f'optional="show"/>'
                )
            else:
                arch_lines.append(
                    f'    <field name="{fname}" '
                    f'string="{label}" '
                    f'width="{auto_width}px" '
                    f'readonly="state != \'draft\'" '
                    f'optional="show"/>'
                )
        
        arch_lines.append('</list>')
        arch = '\n'.join(arch_lines)
        
        view = self.env['ir.ui.view'].sudo().create({
            'name': f'Bảng Chính Sách lương ID {self.id} - {self.name}',
            'model': 'nk.salary.policies',
            'type': 'list',
            'arch': arch,
            'mode': 'primary',
            'priority': 1,
        })
        

        self.env['ir.ui.view'].flush_model()
        
        self.write({'list_view_id': view.id})
        


    def write(self, vals):
        
        LogModel = self.env['nk.salary.policies.log']
        
        for rec in self:
            old_values = {}
            for field_name in vals.keys():
                if field_name in ['write_date', 'write_uid', '__last_update']:
                    continue
                
                field = self._fields.get(field_name)
                if not field:
                    continue
                
                old_val = rec[field_name]
                if old_val is False or old_val is None:
                    old_values[field_name] = ''
                elif field.type == 'many2one':
                    old_values[field_name] = old_val.display_name if old_val else ''
                elif field.type in ('selection', 'boolean', 'integer', 'float', 'monetary'):
                    old_values[field_name] = self._clean_number_str(old_val) if old_val else ''
                else:
                    if field_name == 'dynamic_field_names' and old_val:
                        old_values[field_name] = rec._format_field_names_for_log(old_val)
                    else:
                        old_values[field_name] = str(old_val) if old_val else ''
            
            result = super(NkSalaryImportBatch, rec).write(vals)
            
            for field_name, old_val in old_values.items():
                new_val = rec[field_name]
                
                field = self._fields.get(field_name)
                if new_val is False or new_val is None:
                    new_val_str = ''
                elif field.type == 'many2one':
                    new_val_str = new_val.display_name if new_val else ''
                elif field.type in ('selection', 'boolean', 'integer', 'float', 'monetary'):
                    new_val_str = self._clean_number_str(new_val) if new_val else ''
                else:
                    if field_name == 'dynamic_field_names' and new_val:
                        new_val_str = rec._format_field_names_for_log(new_val)
                    else:
                        new_val_str = str(new_val) if new_val else ''

                old_val_str = str(old_val) if old_val else ''
                if old_val_str == new_val_str:
                    continue
                if field_name == 'state':
                    action_type = 'batch_state_change'
                    state_labels = dict(self._fields['state'].selection)
                    old_display = state_labels.get(old_val_str, old_val_str)
                    new_display = state_labels.get(new_val_str, new_val_str)
                    description = f"Trạng thái Bảng Chính Sách lương thay đổi: {old_display or '(trống)'} → {new_display or '(trống)'}"
                else:
                    action_type = 'batch_field_change'
                    old_display = old_val_str
                    new_display = new_val_str
                    if field_name.startswith('x_'):
                        configs = self.env["nk.salary.policies.field.config"].get_effective_fields(
                            company=rec.company_id,
                            user=self.env.user
                        )
                        config = next((c for c in configs if c.excel_name == field_name), None)
                        field_label = config.display_name if config else field.string or field_name
                    else:
                        field_label = field.string or field_name
                    
                    description = f"Trường '{field_label}' thay đổi: {old_display or '(trống)'} → {new_display or '(trống)'}"
                
                LogModel.create({
                    'batch_id': rec.id,
                    'policies_ids': False,
                    'company_id': rec.company_id.id,
                    'employee_id': False,
                    'log_level': 'batch',
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


    def _format_field_names_for_log(self, field_names_str):

        if not field_names_str:
            return ''
        
        excel_names = [f.strip() for f in field_names_str.split(',') if f.strip()]
        
        if not excel_names:
            return ''
        configs = self.env["nk.salary.policies.field.config"].get_effective_fields(
            company=self.company_id,
            user=self.env.user
        )
        config_map = {c.excel_name: c.display_name for c in configs if c.excel_name}
        display_names = []
        for tech_name in excel_names:
            display_name = config_map.get(tech_name, tech_name)
            display_names.append(display_name)
        
        return ", ".join(display_names)