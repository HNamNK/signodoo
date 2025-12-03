from odoo import api, fields, models, _
from odoo.exceptions import UserError
from lxml import etree
import logging

_logger = logging.getLogger(__name__)


class HrContract(models.Model):
    _inherit = 'hr.contract'

    # XÓA field này vì không đúng cấu trúc
    # salary_policies_ids = fields.One2many(...)
    
    batch_count = fields.Integer(
        string='Số bảng Chính Sách',
        compute='_compute_batch_count'
    )
    


    salary_policies_html = fields.Html(
        string='Chính Sách Lương',
        compute='_compute_salary_policies_html',
        store=False,
        sanitize=False
    )

    @api.depends('employee_id')
    def _compute_batch_count(self):
        """Đếm số batch mà nhân viên có policies in_use/used"""
        for contract in self:
            if contract.employee_id:
                # Lấy các policies của nhân viên có state in_use hoặc used
                policies = self.env['nk.salary.policies'].search([
                    ('employee_id', '=', contract.employee_id.id),
                    ('company_id', '=', contract.company_id.id),
                    ('state', 'in', ['in_use', 'used'])
                ])
                
                # Đếm số batch unique
                batches = policies.mapped('batch_ref_id')
                contract.batch_count = len(batches)
            else:
                contract.batch_count = 0

    @api.depends('employee_id', 'company_id')
    def _compute_latest_salary_policies(self):
        """Lấy policies mới nhất đã approved"""
        for contract in self:
            if contract.employee_id:
                policies = self.env['nk.salary.policies'].search([
                    ('employee_id', '=', contract.employee_id.id),
                    ('company_id', '=', contract.company_id.id),
                    ('state', '=', 'in_use')
                ], order='id desc', limit=1)
                
                contract.latest_salary_policies_id = policies.id if policies else False
            else:
                contract.latest_salary_policies_id = False

    @api.depends('employee_id', 'company_id')
    def _compute_salary_policies_html(self):
        """Render HTML chính sách lương in_use"""
        for contract in self:
            if not contract.employee_id:
                contract.salary_policies_html = "<div class='alert alert-warning'>Chưa chọn nhân viên</div>"
                continue
            
            # Tìm policies in_use
            policies = self.env['nk.salary.policies'].search([
                ('employee_id', '=', contract.employee_id.id),
                ('company_id', '=', contract.company_id.id),
                ('state', '=', 'in_use')
            ], order='id desc', limit=1)
            
            if not policies:
                contract.salary_policies_html = "<div class='alert alert-info'>Nhân viên chưa có chính sách lương đang áp dụng</div>"
                continue
            
            # Lấy batch và configs
            batch = policies.batch_ref_id
            if not batch or not batch.dynamic_field_names:
                contract.salary_policies_html = "<div class='alert alert-info'> chưa có trường động</div>"
                continue
            
            field_names = [f.strip() for f in batch.dynamic_field_names.split(',') if f.strip()]
            configs = self.env['nk.salary.policies.field.config'].search([
                ('technical_name', 'in', field_names)
            ])
            
            if not configs:
                contract.salary_policies_html = "<div class='alert alert-info'>Không tìm thấy cấu hình trường</div>"
                continue
                    
            html = f"<div class='o_group'><h4>Bảng Chính Sách: {batch.name}</h4>"
            html += "<table class='table table-sm table-striped'>"
            
            for cfg in configs:
                value = getattr(policies, cfg.technical_name, False)
                
                # Format value
                if cfg.field_type == 'float':
                    display_value = f"{value:,.2f}" if value else "0.00"
                elif cfg.field_type == 'integer':
                    display_value = f"{value:,}" if value else "0"
                else:
                    display_value = value or ""
                
                html += f"<tr><td><strong>{cfg.display_name}:</strong></td><td>{display_value}</td></tr>"
            
            html += "</table></div>"
            contract.salary_policies_html = html

    def action_view_batches(self):
        """Xem các batch có chính sách lương của nhân viên"""
        self.ensure_one()
        
        if not self.employee_id:
            raise UserError(_("Hợp đồng chưa có nhân viên!"))
        
        # Lấy các policies của nhân viên có state in_use hoặc used
        policies = self.env['nk.salary.policies'].search([
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['in_use', 'used'])
        ])
        
        # Lấy danh sách batch unique
        batches = policies.mapped('batch_ref_id')
        
        if not batches:
            raise UserError(_("Nhân viên chưa có chính sách lương nào đã áp dụng!"))
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Bảng Chính Sách Lương - {self.employee_id.name}',
            'res_model': 'nk.salary.policies.batch',
            'view_mode': 'list,form',
            'domain': [('id', 'in', batches.ids)],
            'context': {
                'default_company_id': self.company_id.id,
                'employee_filter_id': self.employee_id.id,
                'from_contract': True,
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        return contracts

    def write(self, vals):
        return super().write(vals)