from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SignOcaBulkSignWizard(models.TransientModel):
    _name = 'sign.oca.bulk.sign.wizard'
    _description = 'Bulk Sign Wizard'

    signer_ids = fields.Text(string='Signer IDs (JSON)')
    signer_count = fields.Integer(string='Signer Count', readonly=True)
    signature_name = fields.Char(string='Full Name')
    signature_image = fields.Text(string='Signature Image (base64)')
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        signer_ids = self._context.get('active_ids', [])
        
        # Validate signer records exist
        if signer_ids:
            valid_signers = self.env['sign.oca.request.signer'].search([('id', 'in', signer_ids)])
            signer_ids = valid_signers.ids
            _logger.warning("🔍 Found %s valid signers", len(signer_ids))
        
        import json
        res['signer_ids'] = json.dumps(signer_ids)
        res['signer_count'] = len(signer_ids)
        res['signature_name'] = self.env.user.name
        return res
    
    def get_selected_signers(self):
        import json
        signer_ids = json.loads(self.signer_ids or '[]')
        return self.env['sign.oca.request.signer'].browse(signer_ids)

    def action_bulk_sign(self):
        _logger.warning("⚡ signature_image = %s", str(self.signature_image)[:100])
        signers = self.get_selected_signers()
        _logger.warning("📄 Selected signers: %s", signers.ids)
        _logger.warning("📄 Documents to sign: %s", signers.mapped('request_id.name'))
            
        """Thực hiện bulk sign với signature đã nhận"""
        if not self.signature_image:
            raise ValidationError("Chưa có chữ ký. Vui lòng ký trước khi xác nhận.")
            
        results = {'success': [], 'errors': []}
        current_user = self.env.user
        
        for signer in signers:
            try:
                # Kiểm tra signer có thuộc về current user không
                if signer.partner_id != current_user.partner_id.commercial_partner_id:
                    _logger.warning("❌ Signer %s: Không thuộc về user %s", 
                                    signer.id, current_user.name)
                    results['errors'].append(f"{signer.request_id.name}: Không phải signer của bạn")
                    continue

                if not signer.is_allow_signature:
                    _logger.warning("⏩ Signer %s: Chưa đến lượt ký", signer.id)
                    results['errors'].append(f"{signer.request_id.name}: Chưa đến lượt ký")
                    continue

                _logger.warning("✅ Signer %s: Đang build items cho request %s", 
                               signer.id, signer.request_id.name)
                items = self._build_items_for_signer(signer)
                signer.action_sign(items, access_token=False)
                results['success'].append(signer.request_id.name)

            except Exception as e:
                _logger.error("❌ Error signing signer %s: %s", signer.id, str(e))
                results['errors'].append(f"{signer.request_id.name}: {str(e)}")

        return self._show_results(results)
    
    def _build_items_for_signer(self, signer):
        """Build items cho 1 signer cụ thể"""
        items = {}
        request = signer.request_id

        for key, item_data in request.signatory_data.items():
            if item_data.get('role_id') == signer.role_id.id:
                items[key] = item_data.copy()

                if item_data.get('field_type') == 'signature':
                    sig = self.signature_image
                    if sig and sig.startswith("data:image"):
                        sig = sig.split(",", 1)[1]
                    items[key]['value'] = sig
                    _logger.warning("⚡ Cleaned signature base64 (len=%s)", len(sig))
                elif not items[key].get('value'):
                    items[key]['value'] = item_data.get('default_value', '')

        return items
    
    def _show_results(self, results):
        """Hiển thị kết quả"""
        message = []
        
        if results['success']:
            message.append(f"Ký thành công: {len(results['success'])} tài liệu")
        
        if results['errors']:
            message.append(f"Lỗi: {len(results['errors'])} tài liệu")
            for error in results['errors'][:5]:  # Chỉ hiển thị 5 lỗi đầu
                message.append(f"• {error}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bulk Sign',
                'message': '\n'.join(message),
                'type': 'success' if not results['errors'] else 'warning',
                'sticky': True,
            }
        }