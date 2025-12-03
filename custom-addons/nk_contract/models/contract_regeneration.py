# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeContractRegeneration(models.Model):
    """
    Chức năng TÁI TẠO hợp đồng cho nhân viên
    - Chỉ áp dụng cho nhân viên ĐÃ CÓ hợp đồng
    - Kế thừa thông tin department/job/structure từ hợp đồng cũ
    - KHÔNG kiểm tra policies
    """
    _inherit = 'hr.employee'
    
    # ========================================
    # PUBLIC METHODS - REGENERATE
    # ========================================
    
    def regenerate_single_contract(self):
        """
        Tái tạo hợp đồng cho MỘT nhân viên
        
        Raises:
            UserError: Nếu nhân viên chưa có hợp đồng
        """
        self.ensure_one()
        
        # Validation: Nhân viên PHẢI đã có hợp đồng
        if not self.contract_ids:
            raise UserError(_(
                'Nhân viên "%s" chưa có hợp đồng lao động.\n\n'
                'Vui lòng sử dụng chức năng "Tạo hợp đồng mới" '
                'để tạo hợp đồng lần đầu cho nhân viên này.'
            ) % self.name)
        
        _logger.info(f"Regenerating single contract for employee: {self.name}")
        
        return self.regenerate_contracts_batch()
    
    def regenerate_contracts_batch(self):
        """
        Tái tạo hợp đồng HÀNG LOẠT cho nhiều nhân viên
        
        Returns:
            dict: Action notification
            
        Raises:
            UserError: 
                - Nếu không có nhân viên nào được chọn
                - Nếu có nhân viên chưa có hợp đồng
        """
        # Validation 1: Phải có nhân viên được chọn
        if not self:
            raise UserError(_(
                'Vui lòng chọn ít nhất một nhân viên để tái tạo hợp đồng.'
            ))
        
        # Validation 2: TẤT CẢ nhân viên phải đã có hợp đồng
        employees_without_contract = self.filtered(lambda emp: not emp.contract_ids)
        
        if employees_without_contract:
            employee_names = employees_without_contract.mapped('name')
            raise UserError(_(
                'Không thể tái tạo hợp đồng!\n\n'
                'Các nhân viên sau CHƯA CÓ hợp đồng:\n%s\n\n'
                'Vui lòng:\n'
                '• Bỏ chọn các nhân viên này, HOẶC\n'
                '• Sử dụng chức năng "Tạo hợp đồng mới"'
            ) % '\n'.join([f'• {name}' for name in employee_names]))
        
        _logger.info(
            f"Starting batch contract regeneration for {len(self)} employees"
        )
        
        # Danh sách contracts đã tạo
        contracts_created = []
        errors = []
        
        # Loop qua từng nhân viên
        for employee in self:
            try:
                # Bước 1: Lấy hợp đồng hiện tại (mới nhất)
                current_contract = self.env['hr.contract'].search([
                    ('employee_id', '=', employee.id)
                ], limit=1, order='id desc')
                
                if not current_contract:
                    # Trường hợp edge case: contract_ids có nhưng search không ra
                    raise UserError(_(
                        'Không tìm thấy hợp đồng hiện tại của nhân viên "%s"'
                    ) % employee.name)
                
                _logger.debug(
                    f"Found current contract {current_contract.name} "
                    f"for employee {employee.name}"
                )
                
                # Bước 2: Chuẩn bị base values
                contract_vals = employee._prepare_contract_base_vals()
                
                # Bước 3: Thêm thông tin ĐẶC THÙ cho REGENERATE
                # Kế thừa department/job/structure từ HỢP ĐỒNG CŨ
                
                # Department: Ưu tiên từ old contract, fallback employee
                if current_contract.department_id:
                    contract_vals['department_id'] = current_contract.department_id.id
                elif employee.department_id:
                    contract_vals['department_id'] = employee.department_id.id
                
                # Job: Ưu tiên từ old contract, fallback employee
                if current_contract.job_id:
                    contract_vals['job_id'] = current_contract.job_id.id
                elif employee.job_id:
                    contract_vals['job_id'] = employee.job_id.id
                
                # Structure type: Chỉ có trong contract, không có fallback
                if current_contract.structure_type_id:
                    contract_vals['structure_type_id'] = current_contract.structure_type_id.id
                
                # Wage: Kế thừa từ contract cũ
                if current_contract.wage:
                    contract_vals['wage'] = current_contract.wage
                
                _logger.debug(
                    f"Regenerating contract for {employee.name} with vals: {contract_vals}"
                )
                
                # Bước 4: Tạo contract mới
                contract = employee._create_contract_record(contract_vals)
                
                contracts_created.append(contract)
                
                _logger.info(
                    f"✓ Successfully regenerated contract {contract.name} "
                    f"for employee {employee.name} "
                    f"(inherited from {current_contract.name})"
                )
                
            except Exception as e:
                # Lỗi không mong đợi
                error_msg = str(e)
                errors.append(f"• {employee.name}: {error_msg}")
                _logger.exception(
                    f"✗ Unexpected error regenerating contract for {employee.name}"
                )
        
        # Xử lý kết quả
        if errors:
            # Có lỗi xảy ra
            if contracts_created:
                # Một phần thành công, một phần thất bại
                message = _(
                    'Đã tái tạo %d/%d hợp đồng.\n\n'
                    'Các nhân viên sau gặp lỗi:\n%s'
                ) % (
                    len(contracts_created),
                    len(self),
                    '\n'.join(errors)
                )
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Tái tạo hợp đồng một phần thành công'),
                        'message': message,
                        'type': 'warning',
                        'sticky': True,
                    }
                }
            else:
                # Tất cả đều thất bại
                message = _(
                    'Không thể tái tạo hợp đồng cho tất cả nhân viên!\n\n'
                    'Lỗi:\n%s'
                ) % '\n'.join(errors)
                
                raise UserError(message)
        
        # Tất cả thành công
        _logger.info(
            f"✓ Batch regeneration completed: {len(contracts_created)} contracts created"
        )
        
        return self._show_success_notification(contracts_created, 'tái tạo')
    
    # ========================================
    # HELPER METHODS (Private)
    # ========================================
    
    @api.model
    def get_employees_with_contracts(self):
        """
        Lấy danh sách nhân viên ĐÃ CÓ hợp đồng
        
        Returns:
            hr.employee recordset
        """
        return self.search([
            ('contract_ids', '!=', False)
        ])