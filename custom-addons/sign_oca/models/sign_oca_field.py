# Copyright 2023 Dixmit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class SignOcaField(models.Model):
    _name = "sign.oca.field"
    _description = "Signature Field Type"

    name = fields.Char(required=True)
    field_type = fields.Selection(
        [
            ("text", "Text"), 
            ("signature", "Signature"), 
            ("check", "Check"),
            ("auto_fill", "Auto Fill")
        ],
        required=True,
        default="text",
    )
    default_value = fields.Char()
    
    # Auto fill field - chỉ cần lưu field selection
    hr_field_selection = fields.Selection(
        selection='_get_hr_fields_selection',
        string='HR Field'
    )
    
    @api.model
    def _get_hr_fields_selection(self):
        """Lấy tất cả fields từ HR models"""
        selection = []
        
        # Simplified - chỉ lấy các models HR phổ biến
        hr_models = ['hr.employee', 'hr.department', 'hr.job', 'hr.contract','nk.salary.policies']
        
        for model_name in hr_models:
            if model_name not in self.env:
                continue
                
            try:
                model_obj = self.env[model_name]
                model_display = model_name.replace('hr.', '').replace('.', ' ').title()
                
                # ✅ THÊM 'many2one' vào danh sách field types
                for field_name, field_obj in model_obj._fields.items():
                    if field_obj.type in ['char', 'text', 'integer', 'float', 'monetary', 'selection', 'date', 'datetime', 'many2one']:
                        field_key = f"{model_name}.{field_name}"
                        field_label = f"{field_obj.string} ({model_display})"
                        selection.append((field_key, field_label))
            except Exception as e:
                _logger.warning(f"Error loading fields from {model_name}: {e}")
                continue
        
        return sorted(selection, key=lambda x: x[1])

    def get_auto_fill_model_field(self):
        """Parse hr_field_selection to get model and field name"""
        self.ensure_one()
        if not self.hr_field_selection:
            return None, None
        
        # hr_field_selection format: "hr.employee.name" 
        parts = self.hr_field_selection.split('.')
        if len(parts) >= 3:
            model_name = '.'.join(parts[:-1])  # "hr.employee"
            field_name = parts[-1]             # "name"
            return model_name, field_name
        return None, None

    def extract_value_from_record(self, source_record, role_context=None):
        """Extract value from source record or role partner based on context"""
        self.ensure_one()
        
        _logger.info(f"=== EXTRACT DEBUG ===")
        _logger.info(f"Field: {self.name}")
        _logger.info(f"Field type: {self.field_type}")
        _logger.info(f"HR selection: {self.hr_field_selection}")
        _logger.info(f"Source record: {source_record._name}({source_record.id})")
        
        # Early return for non-auto-fill fields
        if self.field_type != 'auto_fill' or not self.hr_field_selection:
            result = self.default_value or ""
            _logger.info(f"Early return: {result}")
            return result
            
        # Special handling for computed fields
        if self.hr_field_selection == 'hr.contract.date_end':
            result = self._compute_contract_date_end(source_record, role_context)
            _logger.info(f"Contract date end: {result}")
            return result
        
        target_model, target_field = self.get_auto_fill_model_field()
        _logger.info(f"Target: {target_model}.{target_field}")
        
        if not target_model or not target_field:
            _logger.warning(f"Invalid hr_field_selection format: {self.hr_field_selection}")
            return self.default_value or ""
        
        try:
            # Role context logic...
            if role_context and role_context.get('role_id'):
                role = self.env['sign.oca.role'].browse(role_context['role_id'])
                partner = role.default_partner_id
                
                if partner and role.partner_selection_policy == 'default':
                    _logger.info(f"Using role-based auto-fill: Role '{role.name}' -> Partner '{partner.name}'")
                    result = self._extract_from_role_partner(partner, target_model, target_field)
                    _logger.info(f"Role-based result: {result}")
                    return result
                    
                elif partner and role.partner_selection_policy == 'expression' and source_record:
                    partner_id = role._get_partner_from_record(source_record)
                    if partner_id:
                        partner = self.env['res.partner'].browse(partner_id)
                        _logger.info(f"Using expression-based role auto-fill: Partner '{partner.name}'")
                        result = self._extract_from_role_partner(partner, target_model, target_field)
                        _logger.info(f"Expression-based result: {result}")
                        return result
            
            # Fallback to source record
            _logger.info(f"Using source_record based auto-fill")
            result = self._extract_from_source_record(source_record, target_model, target_field)
            _logger.info(f"Source-based result: {result}")
            return result
            
        except Exception as e:
            _logger.error(f"Auto fill error for field {self.name} ({self.hr_field_selection}): {e}")
            import traceback
            _logger.error(traceback.format_exc())
            return self.default_value or ""


    def _extract_from_role_partner(self, partner, target_model, target_field):
        """Extract field value from role's partner"""
        if not partner:
            return ""
            
        # Find related employee record from partner
        employee = self.env['hr.employee'].search([('user_id.partner_id', '=', partner.id)], limit=1)
        if not employee:
            # Try alternative relations
            employee = self.env['hr.employee'].search([('address_home_id', '=', partner.id)], limit=1)
        
        if not employee:
            _logger.warning(f"No employee found for partner {partner.name}")
            return ""
        
        # Now extract the field from employee context
        return self._extract_from_source_record(employee, target_model, target_field)
        
    def _extract_from_source_record(self, source_record, target_model, target_field):
        if not source_record:
            return ""
            
        if target_model == source_record._name:
            value = getattr(source_record, target_field, None)
            _logger.debug(f"Direct access - Field: {target_field}, Value: {value}")

            if value is None:
                return self.default_value or ""

            # 🔥 Ưu tiên xử lý recordset ngay từ đây
            if hasattr(value, "_name"):  # Odoo record or recordset
                if not value:
                    return self.default_value or ""
                if len(value) == 1:
                    return value.display_name
                return ", ".join(value.mapped("display_name"))

            # Xử lý primitive
            if isinstance(value, bool):
                return str(value)
            elif isinstance(value, (int, float)):
                return str(int(value)) if isinstance(value, float) and value == int(value) else str(value)
            elif isinstance(value, str):
                return value if value else (self.default_value or "")
            else:
                return str(value) if value else (self.default_value or "")
        
        value = self._find_related_field_value(source_record, target_model, target_field)
        return value or self.default_value or ""

    def _format_recordset_value(self, value):
        """Force any Odoo record/recordset to return display_name(s)"""
        try:
            # Nếu là record hoặc recordset
            if hasattr(value, '_name'):
                if not value:  # rỗng
                    return self.default_value or ""
                if len(value) == 1:
                    return value.display_name
                return ", ".join(value.mapped("display_name"))

            # Nếu không phải recordset (kiểu int, str, bool...)
            return str(value) if value else (self.default_value or "")

        except Exception as e:
            _logger.warning(f"Error formatting recordset value {value}: {e}")
            return self.default_value or ""

    def _get_record_display_value(self, record):
        """Get best display value for a single record"""
        try:
            # Priority order: display_name → name → code → id
            if hasattr(record, 'display_name') and record.display_name:
                return record.display_name
            elif hasattr(record, 'name') and record.name:
                return record.name
            elif hasattr(record, 'code') and record.code:
                return record.code
            else:
                return f"ID: {record.id}"
        except Exception as e:
            _logger.warning(f"Error getting display value for record {record}: {e}")
            try:
                return f"ID: {record.id}"
            except:
                return "N/A"
    def _compute_contract_date_end(self, source_record, role_context=None):
        """Enhanced contract date computation using employee.official_date"""
        try:
            # Determine which record to use for official_date
            work_record = source_record
            
            # If role context provided, try to get employee from role
            if role_context and role_context.get('role_id'):
                role = self.env['sign.oca.role'].browse(role_context['role_id'])
                partner = role.default_partner_id
                
                if partner:
                    # Find employee from partner
                    employee = self.env['hr.employee'].search([('user_id.partner_id', '=', partner.id)], limit=1)
                    if not employee:
                        employee = self.env['hr.employee'].search([('address_home_id', '=', partner.id)], limit=1)
                    
                    if employee:
                        work_record = employee
                        _logger.info(f"Using employee from role for date computation: {employee.name}")
            
            # Get official_date from employee
            official_date = None
            source_model = work_record._name
            
            _logger.debug(f"Computing contract end date using official_date for {source_model}({work_record.id})")
            
            if source_model == 'hr.employee':
                # Direct access to employee's official_date
                official_date = work_record.official_date
                _logger.debug(f"Direct employee access - official_date: {official_date}")
                
            elif source_model == 'hr.contract':
                # Get employee from contract and then official_date
                if work_record.employee_id:
                    official_date = work_record.employee_id.official_date
                    _logger.debug(f"Contract's employee official_date: {official_date}")
                else:
                    _logger.warning("Contract has no employee_id")
                    return ""
                    
            else:
                # Try to find related employee and get official_date
                official_date_str = self._find_related_field_value(work_record, 'hr.employee', 'official_date')
                if not official_date_str:
                    _logger.warning(f"No related employee found for {source_model}")
                    return ""
                official_date = official_date_str
                _logger.debug(f"Related employee official_date: {official_date}")
            
            # Validate official_date
            if not official_date:
                _logger.warning("No official_date available")
                return ""
            
            # Convert date format if needed
            if isinstance(official_date, str):
                from datetime import datetime
                official_date = datetime.strptime(official_date[:10], '%Y-%m-%d').date()
            elif hasattr(official_date, 'date'):
                official_date = official_date.date()
            
            _logger.debug(f"Parsed official_date: {official_date}")
            
            # Get template duration
            template_item = self.env['sign.oca.template.item'].search([('field_id', '=', self.id)], limit=1)
            if not template_item or not template_item.template_id:
                _logger.warning("No template found for this field")
                return ""
                
            template = template_item.template_id
            if not template.contract_type_id or not template.contract_type_id.duration_months:
                _logger.warning(f"No contract_type or duration_months configured in template '{template.name}'")
                return ""
                
            duration_months = template.contract_type_id.duration_months
            _logger.debug(f"Template duration: {duration_months} months")
            
            # Calculate end date using official_date + duration
            from dateutil.relativedelta import relativedelta
            end_date = official_date + relativedelta(months=duration_months)
            result = end_date.strftime('%d/%m/%Y')
            
            _logger.info(f"Calculated contract end date: {official_date} + {duration_months} months = {result}")
            return result
                
        except Exception as e:
            _logger.error(f"Contract end date computation error: {e}")
            import traceback
            _logger.error(traceback.format_exc())
            return ""
    def _find_related_field_value(self, source_record, target_model, target_field):
        """Find value in related models with optimized search - FIXED CONTRACT LOGIC"""
        
        _logger.info(f"=== FIND RELATED DEBUG ===")
        _logger.info(f"Source: {source_record._name}({source_record.id})")
        _logger.info(f"Target: {target_model}.{target_field}")
        
        # Cache field mappings for performance
        relation_fields = []
        for field_name, field_obj in source_record._fields.items():
            if field_obj.comodel_name == target_model:
                relation_fields.append((field_name, field_obj))
                _logger.info(f"Found relation field: {field_name} -> {target_model}")
        
        if not relation_fields:
            _logger.debug(f"No relation found from {source_record._name} to {target_model}")
            return ""
        
        # Process relation fields
        for field_name, field_obj in relation_fields:
            related_records = getattr(source_record, field_name, False)
            _logger.info(f"Processing field: {field_name}, records: {related_records}")
            
            if not related_records:
                _logger.info(f"No records in {field_name}")
                continue
                
            try:
                # Many2one: get first record
                if field_obj.type == 'many2one':
                    raw_value = getattr(related_records, target_field, "")
                    _logger.info(f"Many2one raw value: {raw_value} (type: {type(raw_value)})")
                    
                    # FIXED: Format the value properly
                    formatted_value = self._format_recordset_value(raw_value)
                    _logger.info(f"Many2one formatted value: {formatted_value}")
                    
                    if formatted_value and formatted_value != (self.default_value or ""):
                        return formatted_value
                
                # One2many/Many2many: SPECIAL LOGIC FOR CONTRACTS
                elif field_obj.type in ['one2many', 'many2many']:
                    _logger.info(f"Processing {field_obj.type} field: {field_name}")
                    
                    # Special handling for hr.contract
                    if target_model == 'hr.contract':
                        result = self._get_best_contract_value(related_records, target_field)
                        _logger.info(f"Contract result: {result}")
                        return result
                    
                    # Default logic for other models
                    else:
                        for i, record in enumerate(related_records[:5]):  # Limit to first 5 records for performance
                            raw_value = getattr(record, target_field, "")
                            _logger.info(f"Record {i} raw value: {raw_value} (type: {type(raw_value)})")
                            
                            # FIXED: Format the value properly
                            formatted_value = self._format_recordset_value(raw_value)
                            _logger.info(f"Record {i} formatted value: {formatted_value}")
                            
                            if formatted_value and formatted_value != (self.default_value or ""):
                                return formatted_value
                                
            except Exception as e:
                _logger.warning(f"Error accessing field {target_field} in {field_name}: {e}")
                import traceback
                _logger.error(traceback.format_exc())
                continue
        
        _logger.info("No value found, returning empty")
        return ""
    def _get_best_contract_value(self, contracts, target_field):
        """Get value from best available contract with priority logic"""
        if not contracts:
            return ""
        
        # Priority 1: Running contracts (state = 'open')
        running_contracts = contracts.filtered(lambda c: c.state == 'open')
        if running_contracts:
            # Get latest running contract
            latest_contract = running_contracts.sorted('date_start', reverse=True)[0]
            value = getattr(latest_contract, target_field, "")
            if value:
                _logger.debug(f"Using running contract {latest_contract.id}: {target_field} = {value}")
                return str(value)
        
        # Priority 2: Draft contracts (state = 'draft') 
        draft_contracts = contracts.filtered(lambda c: c.state == 'draft')
        if draft_contracts:
            # Get latest draft contract
            latest_contract = draft_contracts.sorted('date_start', reverse=True)[0] 
            value = getattr(latest_contract, target_field, "")
            if value:
                _logger.debug(f"Using draft contract {latest_contract.id}: {target_field} = {value}")
                return str(value)
        
        # Priority 3: Any other contract
        if contracts:
            latest_contract = contracts.sorted('date_start', reverse=True)[0]
            value = getattr(latest_contract, target_field, "")
            if value:
                _logger.debug(f"Using fallback contract {latest_contract.id}: {target_field} = {value}")
                return str(value)
        
        _logger.warning(f"No suitable contract found for field {target_field}")
        return ""