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
            'state': 'open',
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
        Tạo contract record với quy trình AN TOÀN:
        1. Tạo HĐ mới ở state='draft' (bypass constraint)
        2. Gọi _activate_contract() để xử lý logic chuyển sang 'open'
        
        Returns:
            hr.contract: Contract đã được tạo và kích hoạt (state='open')
        """
        self.ensure_one()
        
        _logger.info(f"🚀 Starting contract creation for employee: {self.name}")
        
        # ===== BƯỚC 1: Tạo HĐ mới ở state='draft' =====
        # QUAN TRỌNG: Luôn tạo ở draft trước để bypass constraint
        contract_vals['state'] = 'draft'
        
        try:
            contract = self.env['hr.contract'].sudo().create(contract_vals)
            
            _logger.info(
                f"✅ Step 1: Created new contract in DRAFT state\n"
                f"   - ID: {contract.id}\n"
                f"   - Name: {contract.name}\n"
                f"   - State: {contract.state}"
            )
            
        except Exception as e:
            _logger.error(
                f"❌ Step 1 FAILED: Cannot create draft contract\n"
                f"Error type: {type(e).__name__}\n"
                f"Error: {str(e)}"
            )
            raise UserError(_(
                'Không thể tạo hợp đồng cho nhân viên "%s".\n'
                'Lỗi: %s'
            ) % (self.name, str(e)))
        
        # ===== BƯỚC 2: Kích hoạt HĐ (draft → open) =====
        try:
            self._activate_contract(contract)
            
            _logger.info(
                f"🎉 Contract creation completed successfully for {self.name}\n"
                f"   - Contract: {contract.name}\n"
                f"   - Final state: {contract.state}"
            )
            
            return contract
            
        except Exception as e:
            # Rollback: Xóa HĐ draft nếu không activate được
            _logger.error(
                f"❌ Step 2 FAILED: Cannot activate contract\n"
                f"Rolling back: Deleting draft contract {contract.name}"
            )
            try:
                contract.sudo().unlink()
            except:
                pass
            raise


    def _activate_contract(self, contract):
        """
        Kích hoạt hợp đồng: chuyển từ draft → open
        Tự động đóng các HĐ cũ nếu có
        
        QUAN TRỌNG: Dùng SQL raw để bypass constraint Odoo
        
        Args:
            contract: hr.contract record (đang ở state='draft')
        
        Returns:
            bool: True nếu thành công
        """
        self.ensure_one()
        
        if contract.state != 'draft':
            _logger.warning(
                f"⚠️ Contract {contract.name} is not in draft state (current: {contract.state})"
            )
            return True
        
        _logger.info(f"🔄 Activating contract {contract.name} (ID: {contract.id}) for employee {self.name}")
        
        # ===== Bước 1: Tìm HĐ cũ cần đóng =====
        old_active_contracts = self.env['hr.contract'].search([
            ('employee_id', '=', self.id),
            ('state', 'not in', ['draft', 'cancel', 'close']),
            ('id', '!=', contract.id)
        ])
        
        _logger.info(
            f"🔍 Found {len(old_active_contracts)} old contract(s) to close:\n"
            f"   {[(c.id, c.name, c.state) for c in old_active_contracts]}"
        )
        
        # ===== Bước 2: Đóng HĐ cũ bằng SQL RAW (bypass constraint) =====
        if old_active_contracts:
            try:
                old_ids = tuple(old_active_contracts.ids)
                
                _logger.info(f"🔧 Closing old contracts using SQL (IDs: {old_ids})")
                
                # QUAN TRỌNG: Dùng SQL UPDATE để bypass constraint
                if len(old_ids) == 1:
                    query = "UPDATE hr_contract SET state = 'close' WHERE id = %s"
                    self.env.cr.execute(query, (old_ids[0],))
                else:
                    query = "UPDATE hr_contract SET state = 'close' WHERE id IN %s"
                    self.env.cr.execute(query, (old_ids,))
                
                # Invalidate cache để ORM biết có thay đổi
                old_active_contracts.invalidate_recordset(['state'])
                self.env['hr.contract'].invalidate_model(['state'])
                
                _logger.info(f"✅ Closed {len(old_active_contracts)} old contract(s) via SQL")
                
            except Exception as e:
                _logger.error(f"❌ Failed to close old contracts: {str(e)}")
                raise UserError(_(
                    'Không thể đóng hợp đồng cũ của nhân viên "%s".\n'
                    'Lỗi: %s'
                ) % (self.name, str(e)))
        else:
            _logger.info("ℹ️ No old contracts to close")
        
        # ===== Bước 3: Kích hoạt HĐ mới =====
        try:
            _logger.info(f"🎯 Activating new contract {contract.name} (ID: {contract.id})")
            
            # QUAN TRỌNG: Dùng context để skip constraint nếu cần
            contract.with_context(bypass_contract_check=True).write({'state': 'open'})
            
            _logger.info(f"✅ Successfully activated contract {contract.name} → state='open'")
            return True
            
        except Exception as e:
            _logger.error(f"❌ Failed to activate contract: {str(e)}")
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



# class HrEmployeeContractWizard(models.TransientModel):
#     """
#     Wizard tạo hợp đồng hàng loạt cho nhân viên
#     """
#     _name = 'hr.employee.contract.wizard'
#     _description = 'Wizard Tạo Hợp Đồng Hàng Loạt'
    
#     # ========================================
#     # FIELDS
#     # ========================================
    
#     employee_ids = fields.Many2many(
#         'hr.employee',
#         string='Nhân viên',
#         required=True,
#         help='Danh sách nhân viên cần tạo hợp đồng'
#     )
    
#     employee_count = fields.Integer(
#         string='Số lượng nhân viên',
#         compute='_compute_employee_count',
#         store=True
#     )
    
#     action_type = fields.Selection([
#         ('create', 'Tạo mới'),
#         ('recreate', 'Tái tạo'),
#     ], string='Loại thao tác', 
#        default='create',
#        required=True)
    
#     # ========================================
#     # COMPUTE METHODS
#     # ========================================
    
#     @api.depends('employee_ids')
#     def _compute_employee_count(self):
#         """Tính số lượng nhân viên được chọn"""
#         for wizard in self:
#             wizard.employee_count = len(wizard.employee_ids)
    
#     # ========================================
#     # ACTION METHODS
#     # ========================================
    
#     def action_process_contracts(self):
#         """
#         Xử lý tạo hợp đồng cho các nhân viên đã chọn
#         """
#         self.ensure_one()
        
#         if not self.employee_ids:
#             raise UserError(_('Vui lòng chọn ít nhất một nhân viên!'))
        
#         _logger.info(
#             f"Processing {self.action_type} contracts for "
#             f"{len(self.employee_ids)} employees"
#         )
        
#         try:
#             if self.action_type == 'create':
#                 # Gọi method tạo hợp đồng hàng loạt
#                 return self.employee_ids.create_contracts_batch()
#             elif self.action_type == 'recreate':
#                 # Gọi method tái tạo hợp đồng (nếu có)
#                 return self.employee_ids.recreate_contracts_batch()
            
#         except UserError as e:
#             # Re-raise UserError để hiển thị message cho user
#             raise
#         except Exception as e:
#             _logger.exception("Error processing contracts in wizard")
#             raise UserError(_(
#                 'Có lỗi xảy ra khi xử lý hợp đồng:\n%s'
#             ) % str(e))