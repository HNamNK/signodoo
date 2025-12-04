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
        KHÃ"NG liên quan đến policies
        
        Returns:
            dict: Base values cho hr.contract.create()
        """
        self.ensure_one()
        
        current_date = datetime.now()
        date_str = current_date.strftime('%d/%m/%Y')
        
        # Xác định công ty: Ưu tiên công ty của employee, fallback về công ty hiện tại
        company = self.company_id or self.env.company
        
        # Chuẩn hóa tên công ty: viết liền không dấu, chữ hoa
        company_code = self._normalize_company_name(company.name)
        
        # Format: [EmployeeID]-DD/MM/YYYY-HDLD-[CONGTY]
        contract_name = f"{self.id}-{date_str}-HDLD-{company_code}"
        
        base_vals = {
            'name': contract_name,
            'employee_id': self.id,
            'date_start': current_date.date(),
            'state': 'draft',
            'company_id': company.id,
            'wage': 0.0,  # Mặc định 0, sẽ được cập nhật sau
        }
        
        _logger.debug(
            f"Prepared base contract vals for employee {self.name}: {contract_name}"
        )
        
        return base_vals

    def _normalize_company_name(self, company_name):
        """
        Chuẩn hóa tên công ty: viết liền không dấu, chữ hoa
        
        Args:
            company_name: str - Tên công ty gốc
            
        Returns:
            str - Tên công ty đã chuẩn hóa
            
        Examples:
            "Nhân Kiệt" -> "NHANKIET"
            "Công ty ABC" -> "CONGTYABC"
            "Đại Phát" -> "DAIPHAT"
        """
        import unicodedata
        
        # Bỏ dấu tiếng Việt
        normalized = unicodedata.normalize('NFD', company_name)
        without_accents = ''.join(
            char for char in normalized 
            if unicodedata.category(char) != 'Mn'
        )
        
        # Chuyển đ -> d, Đ -> D
        without_accents = without_accents.replace('đ', 'd').replace('Đ', 'D')
        
        # Bỏ khoảng trắng và ký tự đặc biệt, chuyển thành chữ hoa
        company_code = ''.join(
            char.upper() for char in without_accents 
            if char.isalnum()
        )
        
        return company_code
    
    def _create_contract_record(self, contract_vals):
        """
        Tạo contract record đơn giản
        
        Args:
            contract_vals: dict values cho contract
            
        Returns:
            hr.contract: Contract record mới tạo
            
        Note:
            - Sử dụng sudo() để admin/HR manager có thể tạo contract 
            cho bất kỳ công ty nào
            - An toàn vì function này được gọi từ wizard có access rights
        """
        self.ensure_one()
        
        # Sử dụng sudo() để bypass multi-company access control
        # Admin/HR Manager cần quyền này để quản lý toàn bộ hệ thống
        contract = self.env['hr.contract'].sudo().create(contract_vals)
        
        _logger.info(
            f"Created contract {contract.id} ({contract.name}) "
            f"for employee {self.name} in company {contract.company_id.name}"
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



class HrEmployeeContractWizard(models.TransientModel):
    """
    Wizard tạo hợp đồng hàng loạt cho nhân viên
    """
    _name = 'hr.employee.contract.wizard'
    _description = 'Wizard Tạo Hợp Đồng Hàng Loạt'
    
    # ========================================
    # FIELDS
    # ========================================
    
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Nhân viên',
        required=True,
        help='Danh sách nhân viên cần tạo hợp đồng'
    )
    
    employee_count = fields.Integer(
        string='Số lượng nhân viên',
        compute='_compute_employee_count',
        store=True
    )
    
    action_type = fields.Selection([
        ('create', 'Tạo mới'),
        ('recreate', 'Tái tạo'),
    ], string='Loại thao tác', 
       default='create',
       required=True)
    
    # ========================================
    # COMPUTE METHODS
    # ========================================
    
    @api.depends('employee_ids')
    def _compute_employee_count(self):
        """Tính số lượng nhân viên được chọn"""
        for wizard in self:
            wizard.employee_count = len(wizard.employee_ids)
    
    # ========================================
    # ACTION METHODS
    # ========================================
    
    def action_process_contracts(self):
        """
        Xử lý tạo hợp đồng cho các nhân viên đã chọn
        """
        self.ensure_one()
        
        if not self.employee_ids:
            raise UserError(_('Vui lòng chọn ít nhất một nhân viên!'))
        
        _logger.info(
            f"Processing {self.action_type} contracts for "
            f"{len(self.employee_ids)} employees"
        )
        
        try:
            if self.action_type == 'create':
                # Gọi method tạo hợp đồng hàng loạt
                return self.employee_ids.create_contracts_batch()
            elif self.action_type == 'recreate':
                # Gọi method tái tạo hợp đồng (nếu có)
                return self.employee_ids.recreate_contracts_batch()
            
        except UserError as e:
            # Re-raise UserError để hiển thị message cho user
            raise
        except Exception as e:
            _logger.exception("Error processing contracts in wizard")
            raise UserError(_(
                'Có lỗi xảy ra khi xử lý hợp đồng:\n%s'
            ) % str(e))