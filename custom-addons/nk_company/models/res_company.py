from odoo import models, api, fields

class ResCompany(models.Model):
    _inherit = "res.company"
    
    company_type = fields.Selection([
        ('state', 'Nhà nước'),
        ('non_state', 'Ngoài nhà nước'),
        ('fdi', 'FDI'),
    ], string="Loại hình công ty")
    
    industry_id = fields.Many2one('nk.company.ics', string="ID ngành nghề")
    
    labor_type = fields.Selection([
        ('hth', 'HTH'),
        ('os', 'OS'),
    ], string="Loại hợp đồng")
    
    manager_email = fields.Char(string="Email người quản lý")
    
    @api.model
    def create(self, vals):
        company = super().create(vals)

        existing = self.env["ir.model.data"].search([
            ("model", "=", "res.company"),
            ("res_id", "=", company.id)
        ], limit=1)

        if not existing:
            xmlid = "company_%s" % company.id
            self.env["ir.model.data"].create({
                "name": xmlid,
                "model": "res.company",
                "module": "__import__",
                "res_id": company.id,
                "noupdate": True,
            })

        return company
