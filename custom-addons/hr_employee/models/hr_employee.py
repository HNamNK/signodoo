import re
from odoo import _, models, fields, api
from odoo.exceptions import UserError, ValidationError
import os


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    ALLOWED_EXTENSIONS_UPLOAD = ['.png', '.jpg', '.jpeg','.pdf', '.doc', '.docx', '.xls', '.xlsx']
    REQUIRED_FIELDS = {
        "name": "Họ và tên",
        "identification": "Số CCCD",
        "identification_id_issue_date": "Ngày cấp CCCD",
        "identification_id_place": "Nơi cấp CCCD",
        "birthday": "Ngày sinh",
        "joining_date": "Ngày vào làm",
        "permanent_address": "Địa chỉ thường trú",
        "mobile_phone": "Di động",
    }
    
    identification = fields.Char(string="Số CCCD", help="Số chứng minh nhân dân", required=True)
    citizen_id_front_image = fields.Binary(string="CCCD mặt trước", help="Hình ảnh mặt trước của CCCD")
    citizen_id_back_image = fields.Binary(string="CCCD mặt sau", help="Hình ảnh mặt sau của CCCD")
    identification_id_issue_date = fields.Date(string="Ngày cấp CCCD", help="Ngày cấp CCCD", required=True)
    identification_id_place = fields.Char(string="Nơi cấp CCCD", help="Nơi cấp CCCD", required=True)

    signature = fields.Binary(string='Chữ ký', attachment=True, help='Tải lên hình ảnh chữ ký của nhân viên (ví dụ: PNG hoặc JPG)')
    signature_filename = fields.Char(string='Tên file chữ ký', help='Tên file của hình ảnh chữ ký')
    attendance_pin = fields.Char(string="Mã chấm công", help="Mã dùng cho mục đích chấm công")
    referral_code = fields.Char(string="Mã giới thiệu", help="Mã giới thiệu nhân viên")
    joining_date = fields.Date(string="Ngày vào làm", help="Ngày bắt đầu hợp đồng của nhân viên", required=True)
    contract_type = fields.Char(string='Loại hợp đồng', help="Loại hợp đồng của nhân viên")
    contract_number = fields.Char(string='Số hợp đồng mới nhất', help="Số hợp đồng mới nhất của nhân viên")
    ethnicity = fields.Char(string="Dân tộc", help="Dân tộc của nhân viên")
    religion = fields.Char(string="Tôn giáo", help="Tôn giáo của nhân viên")
    permanent_address = fields.Char(string="Địa chỉ thường trú", help="Địa chỉ thường trú của nhân viên", required=True)
    current_address = fields.Char(string="Địa chỉ tạm trú", help="Địa chỉ tạm trú của nhân viên")
    health_insurance_number = fields.Char(string="Số sổ BHYT", help="Số sổ bảo hiểm y tế của nhân viên")
    tax_id = fields.Char(string="Mã số thuế", help="Mã số thuế của nhân viên")
    official_date = fields.Date(string="Ngày chính thức", help="Ngày nhân viên trở thành nhân viên chính thức")
    hometown = fields.Char(string="Quê quán", help="Quê quán của nhân viên")
    education_level = fields.Char(string="Trình độ", help="Trình độ học vấn của nhân viên")
    major = fields.Char(string="Chuyên ngành", help="Chuyên ngành học của nhân viên")
    it_skill_level = fields.Char(string="Trình độ tin học", help="Trình độ tin học của nhân viên")
    language_level = fields.Char(string="Trình độ ngoại ngữ", help="Trình độ ngoại ngữ của nhân viên")
    bank_number = fields.Char(string="Số tài khoản ngân hàng", help="Số tài khoản ngân hàng của nhân viên")
    bank_org_id = fields.Many2one('nk.bank', string="Tên ngân hàng")
    bank_branch = fields.Char(string="Chi nhánh ngân hàng", help="Chi nhánh ngân hàng của tài khoản nhân viên")
    bank_code = fields.Char(
        string="Mã ngân hàng",
        related='bank_org_id.code',
        store=False,
        readonly=True,
    )
 
    attached_file = fields.Binary(string="Hồ sơ đính kèm", attachment=True)
    attached_filename = fields.Char("Tên file")
    active = fields.Boolean(readonly=True)

    @api.constrains('identification')
    def _check_identification_length(self):
        for record in self:
            if not re.fullmatch(r'\d{12}', record.identification or ''):
                raise ValidationError("⚠️ Số CCCD phải đúng 12 số. Vui lòng kiểm tra lại!")
            
            
    def action_preview_attached_file(self):
        self.ensure_one()
        if not self.attached_file:
            raise ValidationError("Chưa có file để xem.")
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/hr.employee/{self.id}/attached_file/{self.attached_filename}?download=false",
            'target': 'new',
        }
        
    def action_delete_attached_file(self):
        self.ensure_one()
        attached_filename = self.attached_filename
        
        if not self.attached_file:
            raise ValidationError("Không có file để xóa.")
        self.write({
            'attached_file': False,
            'attached_filename': False,
        })
        current_user = self.env.user
        self.message_post(
            body=_("Hồ sơ đính kèm %s đã được xóa bởi %s." % (attached_filename ,current_user.name)),
            message_type='notification',
        )
        return True
                    
    @api.onchange('attached_file')
    def _onchange_attached_file(self):
        for rec in self:
            if rec.attached_filename:
                ext = os.path.splitext(rec.attached_filename)[1].lower()
                   
                if ext in self.ALLOWED_EXTENSIONS_UPLOAD:
                    employee_name = rec.name.replace(' ', '_') if rec.name else "employee"
                    rec.attached_filename = f"{employee_name}_attached_file{ext}"
                else:
                    raise ValidationError(
                        "Chỉ được phép tải lên file hình ảnh, PDF, Word hoặc Excel. "
                        "File bạn chọn: %s" % rec.attached_filename
                    )
                    
                    
    @api.model
    def load(self, fields, data):
        identification_length_required = 12
        
        allowed_companies = self.env.context.get('allowed_company_ids', False)
        if not allowed_companies:
            raise UserError("Không tìm thấy công ty hiện tại của người dùng.")
        else:
            if len(allowed_companies) > 1:
                raise UserError("Chỉ được phép import cho một công ty duy nhất. Vui lòng chỉ chọn một công ty trước khi import.")
            allowed_company_id = allowed_companies[0]
            
        company_model_data = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'res.company'),
            ('res_id', '=', allowed_company_id)
        ], limit=1)
        company_name = company_model_data.name if company_model_data else 'Công ty không xác định'
    
        
        missing_fields = [f for f in self.REQUIRED_FIELDS if f not in fields]
        if missing_fields:
            readable_missing = ', '.join(self.REQUIRED_FIELDS[f] for f in missing_fields)
            raise UserError(f"File Excel phải chứa các cột bắt buộc: {readable_missing}.")
        
        identification_index = fields.index("identification")
        name_index = fields.index("name")
        bank_number_index = fields.index("bank_number") if "bank_number" in fields else None
        bank_name_index = fields.index("bank_org_id") if "bank_org_id" in fields else None
        
        fields.append('id')
        fields.append('company_id/id')
            
        result = []
        employees_invalid = []
        for row in data:
            if not row or len(row) <= max(identification_index, name_index):
                employee_invalid = {
                    'name': 'Chưa có tên',
                    'identification': 'Không có dữ liệu',
                    'note': 'Hàng dữ liệu không hợp lệ hoặc thiếu thông tin.'
                }
                employees_invalid.append(employee_invalid)
                continue
            
            # Kiểm tra số CCCD
            identification = str(row[identification_index] or '').replace(' ','')
            row[identification_index] = identification
            
            if len(identification) != identification_length_required or not re.fullmatch(r'\d{12}', identification):
                employee_invalid = {
                    'name': row[name_index] if name_index < len(row) else 'Chưa có tên',
                    'identification': identification,
                    'note': f"Số CCCD '{identification}' phải đúng {identification_length_required} số!"
                }
                employees_invalid.append(employee_invalid)
                continue
            
            # Kiểm tra ngân hàng
            if bank_number_index is not None and bank_name_index is not None:
                row[bank_number_index] = str(row[bank_number_index] or '').replace(' ', '')
                bank_name = str(row[bank_name_index]) if bank_name_index < len(row) else ''
                
                if bank_name:
                    bank_info = self.env['nk.bank'].sudo().search([
                        ('key_search', 'ilike', bank_name.replace(' ', '').lower()),
                    ], limit=1)
                    
                    if bank_info:
                        row[bank_name_index] = bank_info.name
                    else:
                        employee_invalid = {
                            'name': row[name_index] if name_index < len(row) else 'Chưa có tên',
                            'identification': identification,
                            'note': f"Tên ngân hàng '{bank_name}' không hợp lệ!"
                        }
                        employees_invalid.append(employee_invalid)
                        continue
                else:
                    row[bank_number_index] = ''
                    
            key_employee = f"{identification}_{allowed_company_id}"
            row.append(key_employee)
            row.append(company_name)
            result.append(row)
            
        load_result = {'ids': [], 'messages': [], 'nextrow': False}
        
        # Nếu có nhân viên không hợp lệ, thêm warning message
        if employees_invalid:
            warning_lines = [
                f"- {emp['name']} (CCCD: {emp['identification']}) - {emp['note']}"
                for emp in employees_invalid
            ]
            
            warning_message = f"Có {len(employees_invalid)} nhân viên không hợp lệ (Các nhân viên này sẽ không được import):\n"
            warning_message += '\n'.join(warning_lines)

            load_result['messages'] = [
                {
                    'type': 'warning',
                    'title': f"{len(employees_invalid)} nhân viên không hợp lệ",
                    'message': warning_message
                },
            ]

        if result:
            super_result = super(HrEmployee, self).load(fields, result)
            load_result['ids'] = super_result.get('ids', [])
            load_result['messages'].extend(super_result.get('messages', []))
            load_result['nextrow'] = super_result.get('nextrow', False)
        
        return load_result