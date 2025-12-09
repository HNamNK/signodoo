from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrEmployeeContractRegeneration(models.Model):
    """
    Chức năng TÁI TẠO hợp đồng cho nhân viên
    - Chỉ áp dụng cho nhân viên ĐÃ CÓ hợp đồng
    - Kế thừa thông tin department/job/structure từ hợp đồng cũ
    - KHÔNG kiểm tra policies
    """
    _inherit = 'hr.employee'
    



    
    def regenerate_single_contract(self):
        """
        Tái tạo hợp đồng cho MỘT nhân viên
        
        Raises:
            UserError: Nếu nhân viên chưa có hợp đồng
        """
        self.ensure_one()
        

        if not self.contract_ids:
            raise UserError(_(
                'Nhân viên "%s" chưa có hợp đồng lao động.\n\n'
                'Vui lòng sử dụng chức năng "Tạo hợp đồng mới" '
                'để tạo hợp đồng lần đầu cho nhân viên này.'
            ) % self.name)
        

        
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

        if not self:
            raise UserError(_(
                'Vui lòng chọn ít nhất một nhân viên để tái tạo hợp đồng.'
            ))
        

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
        

        

        contracts_created = []
        errors = []
        

        for employee in self:
            try:

                current_contract = self.env['hr.contract'].search([
                    ('employee_id', '=', employee.id)
                ], limit=1, order='id desc')
                
                if not current_contract:

                    raise UserError(_(
                        'Không tìm thấy hợp đồng hiện tại của nhân viên "%s"'
                    ) % employee.name)
                
                

                contract_vals = employee._prepare_contract_base_vals()
                


                

                if current_contract.department_id:
                    contract_vals['department_id'] = current_contract.department_id.id
                elif employee.department_id:
                    contract_vals['department_id'] = employee.department_id.id
                

                if current_contract.job_id:
                    contract_vals['job_id'] = current_contract.job_id.id
                elif employee.job_id:
                    contract_vals['job_id'] = employee.job_id.id
                

                if current_contract.structure_type_id:
                    contract_vals['structure_type_id'] = current_contract.structure_type_id.id
                

                if current_contract.wage:
                    contract_vals['wage'] = current_contract.wage
            
                contract = employee._create_contract_record(contract_vals)


                # if contract.state != 'open':

                contracts_created.append(contract)
                
                
            except Exception as e:

                import traceback
                error_msg = str(e)
                full_traceback = traceback.format_exc()
                
                errors.append(f"• {employee.name}: {error_msg}")
                

        

        if errors:

            if contracts_created:

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

                message = _(
                    'Không thể tái tạo hợp đồng cho tất cả nhân viên!\n\n'
                    'Lỗi:\n%s'
                ) % '\n'.join(errors)
                
                raise UserError(message)
        
        
        return self._show_success_notification(contracts_created, 'tái tạo')
    



    
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