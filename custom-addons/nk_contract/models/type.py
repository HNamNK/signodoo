
from odoo import models, fields, api

class HrContractType(models.Model):
    _inherit = 'hr.contract.type'
    
    duration_months = fields.Integer(
        string='Tháng',
        help='Số Tháng của Loại Hợp đồng này',
    )