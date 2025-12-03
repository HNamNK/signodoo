# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeContractBase(models.Model):
    """
    Base class chứa logic CHUNG cho contract management
    - KHÔNG kiểm tra policies
    - CHỈ tạo/tái tạo hợp đồng
    """
    _inherit = 'hr.employee'
    
    # ========================================
    # HELPER METHODS (Shared)
    # ========================================
    
    def _prepare_contract_base_vals(self):
        """
        Chuẩn bị values CƠ BẢN cho contract
        KHÔNG liên quan đến policies
        
        Returns:
            dict: Base values cho hr.contract.create()
        """
        self.ensure_one()
        
        current_date = datetime.now()
        date_str = current_date.strftime('%d/%m/%Y')
        
        # Format: [EmployeeID]-DD/MM/YYYY-HDLD-NK
        contract_name = f"{self.id}-{date_str}-HDLD-NK"
        
        base_vals = {
            'name': contract_name,
            'employee_id': self.id,
            'date_start': current_date.date(),
            'state': 'draft',
            'company_id': self.company_id.id or self.env.company.id,
            'wage': 0.0,  # Mặc định 0, sẽ được cập nhật sau
        }
        
        _logger.debug(
            f"Prepared base contract vals for employee {self.name}: {contract_name}"
        )
        
        return base_vals
    
    def _create_contract_record(self, contract_vals):
        """
        Tạo contract record đơn giản
        
        Args:
            contract_vals: dict values cho contract
            
        Returns:
            hr.contract: Contract record mới tạo
        """
        self.ensure_one()
        
        contract = self.env['hr.contract'].create(contract_vals)
        
        _logger.info(
            f"Created contract {contract.id} ({contract.name}) "
            f"for employee {self.name}"
        )
        
        return contract
    
    def _show_success_notification(self, contracts_created, action_type='tạo'):
        """
        Hiển thị notification sau khi tạo/tái tạo contract
        
        Args:
            contracts_created: list of hr.contract records
            action_type: str ('tạo' hoặc 'tái tạo')
            
        Returns:
            dict: Action notification
        """
        if not contracts_created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Cảnh báo!'),
                    'message': _('Không có hợp đồng nào được tạo.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Tạo message chi tiết
        contract_details = []
        for contract in contracts_created:
            contract_details.append(
                f"• {contract.name} - {contract.employee_id.name}"
            )
        
        message = _(
            'Đã %s thành công %d hợp đồng:\n\n%s'
        ) % (
            action_type,
            len(contracts_created),
            '\n'.join(contract_details)
        )
        
        _logger.info(
            f"Successfully {action_type} {len(contracts_created)} contracts"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('%s hợp đồng thành công!') % action_type.capitalize(),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }
    
    # ========================================
    # VIEW ACTIONS (Optional - Helper)
    # ========================================
    
    def action_view_contracts(self):
        """
        Xem danh sách hợp đồng của nhân viên
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hợp đồng của %s') % self.name,
            'res_model': 'hr.contract',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }