from odoo import models, fields

class NkBank(models.Model):
    _name = 'nk.bank'
    _description = 'Bank VietNam'
    _table = 'nk_bank_org'
    _auto = False
    
    name = fields.Char(required=True, string="Tên ngân hàng")
    sort_name = fields.Char(required=True, string="Tên viết tắt")
    code = fields.Char(string="Mã ngân hàng", help="Mã định danh của ngân hàng")
    key_search = fields.Char(string="Từ khóa tìm kiếm", help="Từ khóa để tìm kiếm ngân hàng")
    
    
    