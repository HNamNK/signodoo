from odoo import api, fields, models, _
from odoo.exceptions import UserError
from lxml import etree
import logging

_logger = logging.getLogger(__name__)


class HrContract(models.Model):
    _inherit = 'hr.contract'



    
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
    _sql_constraints = [
        ('date_check', 
        "CHECK((date_end IS NULL) OR (date_start <= date_end))", 
        'Contract start date must be earlier than contract end date.'),
    ]

    @api.depends('employee_id')
    def _compute_batch_count(self):
        """Đếm số batch mà nhân viên có policies in_use/used"""
        for contract in self:
            if contract.employee_id:

                policies = self.env['nk.salary.policies'].search([
                    ('employee_id', '=', contract.employee_id.id),
                    ('company_id', '=', contract.company_id.id),
                    ('state', 'in', ['in_use', 'used'])
                ])
                

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

    @api.depends('employee_id', 'company_id', 'state', 'create_date')
    def _compute_salary_policies_html(self):
        """
        Render HTML chính sách lương theo 7 CASE
        """
        for contract in self:
            if not contract.employee_id:
                contract.salary_policies_html = "<div class='alert alert-warning'>Chưa chọn nhân viên</div>"
                continue
            

            if contract.state == 'open':

                policies = self.env['nk.salary.policies'].search([
                    ('employee_id', '=', contract.employee_id.id),
                    ('company_id', '=', contract.company_id.id),
                    ('state', '=', 'in_use'),
                    ('activated_date', '!=', False),
                    ('activated_date', '>=', contract.create_date),
                ], order='activated_date desc', limit=1)
                
                if not policies:

                    contract.salary_policies_html = (
                        "<div class='alert alert-info'>"
                        "Chưa có chính sách lương áp dụng sau khi hợp đồng được tạo"
                        "</div>"
                    )
                    continue
            
            elif contract.state == 'close':

                next_contract = contract._get_next_contract()
                
                if next_contract:

                    policies = self.env['nk.salary.policies'].search([
                        ('employee_id', '=', contract.employee_id.id),
                        ('company_id', '=', contract.company_id.id),
                        ('state', 'in', ['in_use', 'used']),
                        ('activated_date', '!=', False),
                        ('activated_date', '>=', contract.create_date),
                        ('activated_date', '<', next_contract.create_date),
                    ], order='activated_date desc', limit=1)
                    
                    if not policies:

                        contract.salary_policies_html = (
                            "<div class='alert alert-info'>"
                            "Hợp đồng kết thúc trước khi có chính sách lương"
                            "</div>"
                        )
                        continue
                else:

                    policies = self.env['nk.salary.policies'].search([
                        ('employee_id', '=', contract.employee_id.id),
                        ('company_id', '=', contract.company_id.id),
                        ('state', 'in', ['in_use', 'used']),
                        ('activated_date', '!=', False),
                        ('activated_date', '>=', contract.create_date),
                    ], order='activated_date desc', limit=1)
                    
                    if not policies:
                        contract.salary_policies_html = (
                            "<div class='alert alert-info'>"
                            "Hợp đồng chưa có chính sách lương được áp dụng"
                            "</div>"
                        )
                        continue
            
            else:

                contract.salary_policies_html = (
                    "<div class='alert alert-secondary'>"
                    f"Hợp đồng đang ở trạng thái: {dict(contract._fields['state'].selection).get(contract.state)}"
                    "</div>"
                )
                continue
            

            batch = policies.batch_ref_id
            if not batch or not batch.dynamic_field_names:
                contract.salary_policies_html = (
                    "<div class='alert alert-info'>Chính sách chưa có trường động</div>"
                )
                continue
            

            state_badge = self._get_policy_state_badge(policies.state)
            

            field_names = [f.strip() for f in batch.dynamic_field_names.split(',') if f.strip()]
            configs = self.env['nk.salary.policies.field.config'].search([
                ('technical_name', 'in', field_names)
            ])
            
            if not configs:
                contract.salary_policies_html = (
                    "<div class='alert alert-info'>Không tìm thấy cấu hình trường</div>"
                )
                continue
            
            html = f"<div class='o_group'>"
            html += f"<h4>Bảng Chính Sách: {batch.name} {state_badge}</h4>"
            html += f"<p><small>Ngày kích hoạt: {policies.activated_date.strftime('%d/%m/%Y %H:%M') if policies.activated_date else 'N/A'}</small></p>"
            html += "<table class='table table-sm table-striped'>"
            
            for cfg in configs:
                value = getattr(policies, cfg.technical_name, False)
                

                if cfg.field_type == 'float':
                    display_value = f"{value:,.2f}" if value else "0.00"
                elif cfg.field_type == 'integer':
                    display_value = f"{value:,}" if value else "0"
                else:
                    display_value = value or ""
                
                html += f"<tr><td><strong>{cfg.display_name}:</strong></td><td>{display_value}</td></tr>"
            
            html += "</table></div>"
            contract.salary_policies_html = html

    def _get_next_contract(self):
        """
        Tìm hợp đồng KẾ TIẾP của cùng nhân viên
        
        Returns:
            hr.contract | False: HĐ kế tiếp hoặc False nếu không có
        """
        self.ensure_one()
        
        if not self.employee_id:
            return False
        
        next_contract = self.env['hr.contract'].search([
            ('employee_id', '=', self.employee_id.id),
            ('create_date', '>', self.create_date),
        ], order='create_date asc', limit=1)
        
        return next_contract if next_contract else False



    def _get_policy_state_badge(self, state):
        """
        Hiển thị badge cho state của CSL
        
        Args:
            state: 'in_use' hoặc 'used'
        
        Returns:
            str: HTML badge
        """
        if state == 'in_use':
            return "<span class='badge badge-success'>Đang áp dụng</span>"
        elif state == 'used':
            return "<span class='badge badge-secondary'>Đã áp dụng</span>"
        else:
            return ""

    def action_view_batches(self):
        """Xem các batch có chính sách lương của nhân viên"""
        self.ensure_one()
        
        if not self.employee_id:
            raise UserError(_("Hợp đồng chưa có nhân viên!"))
        

        policies = self.env['nk.salary.policies'].search([
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['in_use', 'used'])
        ])
        

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



    @api.constrains('state', 'employee_id')
    def _check_current_contract(self):
        """
        Override để hỗ trợ bypass context
        """
        if self.env.context.get('bypass_contract_check'):

            return
        

        return super()._check_current_contract()