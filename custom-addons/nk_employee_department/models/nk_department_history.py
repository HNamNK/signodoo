from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

class HrDepartmentHistory(models.Model):
    _name = 'nk.department.history'
    _description = 'Department Transfer History'
    _order = 'date_start desc'

    employee_id = fields.Many2one(
        'hr.employee', 
        string='Nhân viên',  
        required=True, 
        ondelete='cascade',
        index=True
    )
    department_id = fields.Many2one(
        'hr.department', 
        string='Phòng ban', 
        required=False,
        ondelete='set null'
    )
    department_name = fields.Char(
        string='Tên phòng ban',
        store=True
    )
    department_display = fields.Char(
        string='Phòng ban',
        compute='_compute_department_display',
        store=True
    )
    date_start = fields.Date(
        string='Ngày bắt đầu', 
        required=True,
        default=fields.Date.today
    )
    date_end = fields.Date(
        string='Ngày kết thúc'
    )
    notes = fields.Text(
        string='Ghi chú'
    )
    duration = fields.Char(
        string='Thời gian làm việc',
        compute='_compute_duration',
        store=True
    )
    status = fields.Char(
        string='Trạng thái',
        compute='_compute_status',
        store=True
    )
    
    _sql_constraints = [
        ('check_dates', 
         'CHECK(date_end IS NULL OR date_end >= date_start)', 
         'Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu!')
    ]

    @api.depends('department_id', 'department_name')
    def _compute_department_display(self):
        for record in self:
            if record.department_id:
                record.department_display = record.department_id.name
            elif record.department_name:
                record.department_display = f"{record.department_name} (Đã xóa)"
            else:
                record.department_display = "Không xác định"

    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        for record in self:
            if record.date_start:
                if not record.date_end:
                    record.duration = ""
                else:
                    delta = relativedelta(record.date_end, record.date_start)
                    
                    years = delta.years
                    months = delta.months
                    days = delta.days

                    duration_parts = []
                    if years > 0:
                        duration_parts.append(f"{years} năm")
                    if months > 0:
                        duration_parts.append(f"{months} tháng")
                    if days >= 0:
                        duration_parts.append(f"{days} ngày")
                    
                    record.duration = " ".join(duration_parts) if duration_parts else ""
            else:
                record.duration = ""

    @api.depends('date_end')
    def _compute_status(self):
        for record in self:
            if not record.date_end:
                record.status = "Đang làm việc"
            else:
                record.status = "Đã chuyển"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('department_id') and not vals.get('department_name'):
                department = self.env['hr.department'].browse(vals['department_id'])
                vals['department_name'] = department.name
        
        records = super(HrDepartmentHistory, self).create(vals_list)
        
        for record in records:
            if record.employee_id:
                record.employee_id.message_post(
                    body=(
                        Markup("- <b>Phòng ban:</b> ") + Markup.escape(record.department_display) + Markup("<br/>")
                        + Markup("- <b>Ngày bắt đầu:</b> ") + Markup.escape(str(record.date_start)) + Markup("<br/>")
                        + Markup("- <b>Ghi chú:</b> ") + Markup.escape(record.notes or 'Không có') + Markup("<br/>")
                        + Markup("- <b>Người tạo:</b> ") + Markup.escape(self.env.user.name)
                    ),
                    subject="Tạo mới lịch sử phòng ban",
                    message_type='comment',
                    subtype_id=self.env.ref('mail.mt_note').id,
                )
        
        return records

    def write(self, vals):
        old_values = {}
        for record in self:
            old_values[record.id] = {
                'department_display': record.department_display,
                'date_start': record.date_start,
                'date_end': record.date_end,
                'notes': record.notes,
            }
        
        if vals.get('department_id'):
            department = self.env['hr.department'].browse(vals['department_id'])
            vals['department_name'] = department.name
        
        result = super(HrDepartmentHistory, self).write(vals)
        
        for record in self:
            old_data = old_values.get(record.id, {})
            changes = []
            
            if ('department_id' in vals or 'department_name' in vals) and old_data.get('department_display') != record.department_display:
                changes.append(Markup("- <b>Phòng ban:</b> ") + Markup.escape(old_data.get('department_display')) + Markup(" → ") + Markup.escape(record.department_display))
            
            if 'date_start' in vals and old_data.get('date_start') != record.date_start:
                changes.append(Markup("- <b>Ngày bắt đầu:</b> ") + Markup.escape(str(old_data.get('date_start'))) + Markup(" → ") + Markup.escape(str(record.date_start)))
            
            if 'date_end' in vals:
                old_date_end = old_data.get('date_end') or 'Chưa có'
                new_date_end = record.date_end or 'Chưa có'
                if old_date_end != new_date_end:
                    changes.append(Markup("- <b>Ngày kết thúc:</b> ") + Markup.escape(str(old_date_end)) + Markup(" → ") + Markup.escape(str(new_date_end)))
            
            if 'notes' in vals and old_data.get('notes') != record.notes:
                old_notes = old_data.get('notes') or 'Không có'
                new_notes = record.notes or 'Không có'
                changes.append(Markup("- <b>Ghi chú:</b> ") + Markup.escape(old_notes) + Markup(" → ") + Markup.escape(new_notes))
            
            if changes and record.employee_id:
                record.employee_id.message_post(
                    body=(
                        Markup("<br/>").join(changes) + Markup("<br/>")
                        + Markup("- <b>Người cập nhật:</b> ") + Markup.escape(self.env.user.name)
                    ),
                    subject="Cập nhật lịch sử phòng ban",
                    message_type='comment',
                    subtype_id=self.env.ref('mail.mt_note').id,
                )
        
        return result

    def unlink(self):
        for record in self:
            employee = record.employee_id
            department_display = record.department_display
            date_start = record.date_start
            date_end = record.date_end or 'Chưa có'
            
            if employee:
                employee.message_post(
                    body=(
                        Markup("- <b>Phòng ban:</b> ") + Markup.escape(department_display) + Markup("<br/>")
                        + Markup("- <b>Ngày bắt đầu:</b> ") + Markup.escape(str(date_start)) + Markup("<br/>")
                        + Markup("- <b>Ngày kết thúc:</b> ") + Markup.escape(str(date_end)) + Markup("<br/>")
                        + Markup("- <b>Người xóa:</b> ") + Markup.escape(self.env.user.name)
                    ),
                    subject="Xóa lịch sử phòng ban",
                    message_type='comment',
                    subtype_id=self.env.ref('mail.mt_note').id,
                )
        
        return super(HrDepartmentHistory, self).unlink()