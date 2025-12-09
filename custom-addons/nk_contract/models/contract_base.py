from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime


class HrEmployeeContractBase(models.Model):
    """
    Base class chứa logic CHUNG cho contract management
    - KHÔNG kiểm tra policies
    - CHỈ tạo/tái tạo hợp đồng
    """
    _inherit = 'hr.employee'
    
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
        company = self.company_id or self.env.company        
        company_code = self._normalize_company_name(company.name)        
        contract_name = f"{self.id}-{date_str}-HDLD-{company_code}"
        
        base_vals = {
            'name': contract_name,
            'employee_id': self.id,
            'date_start': current_date.date(),
            'state': 'open',
            'company_id': company.id,
            'wage': 0.0,        }

        
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
        normalized = unicodedata.normalize('NFD', company_name)
        without_accents = ''.join(
            char for char in normalized 
            if unicodedata.category(char) != 'Mn'
        )
        
        without_accents = without_accents.replace('đ', 'd').replace('Đ', 'D')
        
        company_code = ''.join(
            char.upper() for char in without_accents 
            if char.isalnum()
        )
        
        return company_code
    
    def _create_contract_record(self, contract_vals):
        """
        Tạo contract record với quy trình AN TOÀN:
        1. Tạo HĐ mới ở state='draft' (bypass constraint)
        2. Gọi _activate_contract() để xử lý logic chuyển sang 'open'
        
        Returns:
            hr.contract: Contract đã được tạo và kích hoạt (state='open')
        """
        self.ensure_one()
        

        
        contract_vals['state'] = 'draft'
        
        try:
            contract = self.env['hr.contract'].sudo().create(contract_vals)
            
            
        except Exception as e:


            raise UserError(_(
                'Không thể tạo hợp đồng cho nhân viên "%s".\n'
                'Lỗi: %s'
            ) % (self.name, str(e)))
        
        try:
            self._activate_contract(contract)
            
            
            return contract
            
        except Exception as e:

            try:
                contract.sudo().unlink()
            except:
                pass
            raise


    def _activate_contract(self, contract):
        self.ensure_one()
        
        if contract.state != 'draft':
            return True
        
        # Đóng HĐ cũ
        old_active_contracts = self.env['hr.contract'].search([
            ('employee_id', '=', self.id),
            ('state', 'not in', ['draft', 'cancel', 'close']),
            ('id', '!=', contract.id)
        ])
        
        if old_active_contracts:
            try:
                old_ids = tuple(old_active_contracts.ids)
                if len(old_ids) == 1:
                    query = "UPDATE hr_contract SET state = 'close' WHERE id = %s"
                    self.env.cr.execute(query, (old_ids[0],))
                else:
                    query = "UPDATE hr_contract SET state = 'close' WHERE id IN %s"
                    self.env.cr.execute(query, (old_ids,))
                
                old_active_contracts.invalidate_recordset(['state'])
                self.env['hr.contract'].invalidate_model(['state'])
                
            except Exception as e:
                raise UserError(_(
                    'Không thể đóng hợp đồng cũ của nhân viên "%s".\n'
                    'Lỗi: %s'
                ) % (self.name, str(e)))
        
        # ===== PHẦN BỊ THIẾU - KÍCH HOẠT CONTRACT MỚI =====
        try:
            contract.with_context(bypass_contract_check=True).write({'state': 'open'})
            return True
            
        except Exception as e:
            raise UserError(_(
                'Không thể kích hoạt hợp đồng mới cho nhân viên "%s".\n'
                'Lỗi: %s'
            ) % (self.name, str(e)))

    
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
 
    @api.model
    def action_open_contract_create_wizard_from_selection(self, employee_ids):
        """
        Mở wizard tạo hợp đồng từ JS selection
        """
        employees = self.browse(employee_ids)
        
        if not employees:
            raise UserError("Vui lòng chọn ít nhất một nhân viên để tạo hợp đồng.")
        
        employees_without_contract = employees.filtered(lambda e: not e.contract_ids)
        
        if not employees_without_contract:
            raise UserError(
                "Không có nhân viên nào trong danh sách đã chọn CHƯA CÓ hợp đồng.\n\n"
                "Vui lòng sử dụng chức năng 'Tái tạo hợp đồng' cho nhân viên đã có hợp đồng."
            )
        
        wizard = self.env['hr.employee.contract.wizard'].create({
            'employee_ids': [(6, 0, employees_without_contract.ids)],
            'action_type': 'create',
        })
        
        return {
            'name': 'Tạo Hợp Đồng Hàng Loạt',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.contract.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],  # ← THÊM DÒNG NÀY
            'target': 'new',
            'res_id': wizard.id,
            'context': dict(self.env.context, default_action_type='create')
        }

    @api.model
    def action_open_contract_regenerate_wizard_from_selection(self, employee_ids):
        """
        Mở wizard tái tạo hợp đồng từ JS selection
        """
        employees = self.browse(employee_ids)
        
        if not employees:
            raise UserError("Vui lòng chọn ít nhất một nhân viên để tái tạo hợp đồng.")
        
        employees_with_contract = employees.filtered(lambda e: e.contract_ids)
        
        if not employees_with_contract:
            raise UserError(
                "Không có nhân viên nào trong danh sách đã chọn ĐÃ CÓ hợp đồng.\n\n"
                "Vui lòng sử dụng chức năng 'Tạo hợp đồng mới' cho nhân viên chưa có hợp đồng."
            )
        
        wizard = self.env['hr.employee.contract.wizard'].create({
            'employee_ids': [(6, 0, employees_with_contract.ids)],
            'action_type': 'regenerate',
        })
        
        return {
            'name': 'Tái Tạo Hợp Đồng Hàng Loạt',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.contract.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],  # ← THÊM DÒNG NÀY
            'target': 'new',
            'res_id': wizard.id,
            'context': dict(self.env.context, default_action_type='regenerate')
        }