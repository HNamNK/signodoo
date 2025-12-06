from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrEmployeeContractCreate(models.Model):
    """
    Chức năng TẠO MỚI hợp đồng cho nhân viên
    - Chỉ áp dụng cho nhân viên CHƯA CÓ hợp đồng
    - KHÔNG kiểm tra policies
    """
    _inherit = 'hr.employee'
    



    
    def create_single_contract(self):
        """
        Tạo hợp đồng cho MỘT nhân viên
        
        Raises:
            UserError: Nếu nhân viên đã có hợp đồng
        """
        self.ensure_one()
        

        if self.contract_ids:
            raise UserError(_(
                'Nhân viên "%s" đã có hợp đồng lao động.\n\n'
                'Vui lòng sử dụng chức năng "Tái tạo hợp đồng" '
                'để tạo hợp đồng mới cho nhân viên này.'
            ) % self.name)
        

        
        return self.create_contracts_batch()
    
    def create_contracts_batch(self):
        """
        Tạo hợp đồng HÀNG LOẠT cho nhiều nhân viên
        
        Returns:
            dict: Action notification
            
        Raises:
            UserError: 
                - Nếu không có nhân viên nào được chọn
                - Nếu có nhân viên đã có hợp đồng
        """

        if not self:
            raise UserError(_(
                'Vui lòng chọn ít nhất một nhân viên để tạo hợp đồng.'
            ))
        

        employees_with_contract = self.filtered(lambda emp: emp.contract_ids)
        
        if employees_with_contract:
            employee_names = employees_with_contract.mapped('name')
            raise UserError(_(
                'Không thể tạo hợp đồng!\n\n'
                'Các nhân viên sau ĐÃ CÓ hợp đồng:\n%s\n\n'
                'Vui lòng:\n'
                '• Bỏ chọn các nhân viên này, HOẶC\n'
                '• Sử dụng chức năng "Tái tạo hợp đồng"'
            ) % '\n'.join([f'• {name}' for name in employee_names]))
        

        

        contracts_created = []
        errors = []
        

        for employee in self:
            try:

                contract_vals = employee._prepare_contract_base_vals()
                


                if employee.department_id:
                    contract_vals['department_id'] = employee.department_id.id
                    
                if employee.job_id:
                    contract_vals['job_id'] = employee.job_id.id

                

                contract = employee._create_contract_record(contract_vals)
                
                contracts_created.append(contract)
                

                
            except Exception as e:

                error_msg = str(e)
                errors.append(f"• {employee.name}: {error_msg}")


        

        if errors:

            if contracts_created:

                message = _(
                    'Đã tạo %d/%d hợp đồng.\n\n'
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
                        'title': _('Tạo hợp đồng một phần thành công'),
                        'message': message,
                        'type': 'warning',
                        'sticky': True,
                    }
                }
            else:

                message = _(
                    'Không thể tạo hợp đồng cho tất cả nhân viên!\n\n'
                    'Lỗi:\n%s'
                ) % '\n'.join(errors)
                
                raise UserError(message)

        
        return self._show_success_notification(contracts_created, 'tạo')
    



    
    @api.model
    def get_employees_without_contracts(self):
        """
        Lấy danh sách nhân viên CHƯA CÓ hợp đồng
        
        Returns:
            hr.employee recordset
        """
        return self.search([
            ('contract_ids', '=', False)
        ])