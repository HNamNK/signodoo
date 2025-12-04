from odoo import models, fields, api

class NkCompanyIcs(models.Model):
    _name = 'nk.company.ics'
    _description = 'NK Company ICS'
    _table = 'nk_company_ics'
    _auto = False
    _rec_name = 'display_name'

    name = fields.Char(string="Tên ngành", required=True)
    code = fields.Char(string="Mã ngành", required=True)
    parent_code = fields.Many2one('nk.company.ics')
    
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=False)
    
    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code} - {rec.name}" if rec.code else rec.name
    
    def name_get(self):
        result = []
        for rec in self:
            display = f"{rec.code} - {rec.name}" if rec.code else rec.name
            result.append((rec.id, display))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Override name_search để search theo cả code và name"""
        args = list(args or [])
        
        if name:
            if ' - ' in name:
                code_part = name.split(' - ')[0].strip()
                name_part = ' - '.join(name.split(' - ')[1:]).strip()
                domain = [
                    '|',
                    ('code', operator, code_part),
                    ('name', operator, name_part)
                ]
            else:
                domain = [
                    '|',
                    ('code', operator, name),
                    ('name', operator, name)
                ]
            args = domain + args
        
        records = self.search(args, limit=limit)
        return records.name_get()