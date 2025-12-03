/** @odoo-module **/

import { Component, useState, useRef, onMounted, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";


export class NullFloatField extends Component {
    static template = "nk_salary.NullFloatField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.inputRef = useRef("numericInput");
        
        this.state = useState({});

        onMounted(() => {
            this.updateInputValue();
        });

        onPatched(() => {
            this.updateInputValue();
        });
    }

    updateInputValue() {
        if (this.inputRef.el && document.activeElement !== this.inputRef.el) {
            this.inputRef.el.value = this.formattedValue;
        }
    }

    get fieldValue() {
        if (!this.props.record || !this.props.record.data) {
            return false;
        }
        return this.props.record.data[this.props.name];
    }

    get isNull() {
        const val = this.fieldValue;
        return val === false || val === null || val === undefined;
    }

    get formattedValue() {
        const val = this.fieldValue;
        
        if (typeof val === 'number' && val !== 0) {
            if (Math.abs(val) < 1) {
                return (val * 100).toLocaleString("vi-VN", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                }) + "%";
            }
            
            const isInteger = val === Math.floor(val);
            
            return val.toLocaleString("vi-VN", {
                minimumFractionDigits: 0,
                maximumFractionDigits: isInteger ? 0 : 6,
                useGrouping: true
            });
        }
        
        if (val === 0 && !this.isNull) {
            return "0";
        }
        
        return "";
    }

    get displayValue() {
        return this.formattedValue;
    }

    get isReadonly() {
        return this.props.readonly;
    }

    parse(value) {
        const input = (value || "").trim();
        
        if (!input) {
            return 0; 
        }
        
        let cleaned = input.replace(/\s/g, '');  
        let parsed = 0;
        
        if (cleaned.includes("%")) {
            const numStr = cleaned.replace("%", "").replace(/\./g, '').replace(/,/g, '.');
            parsed = parseFloat(numStr) / 100;
        } else {
            cleaned = cleaned.replace(/\./g, '').replace(/,/g, '.');
            parsed = parseFloat(cleaned);
            
            if (!isNaN(parsed) && parsed > 1 && parsed < 100) {
                parsed = parsed / 100;
            }
        }
        
        if (isNaN(parsed)) {
            return 0; 
        }
        
        return parsed;
    }

    onFocus(ev) {
        if (this.isReadonly) return;
        
        const input = ev.target;
        setTimeout(() => input.select(), 0);
    }

    async onChange(ev) {
        if (this.isReadonly) return;
        
        const rawValue = ev.target.value;
        const parsed = this.parse(rawValue);
        
        await this.props.record.update({ 
            [this.props.name]: parsed 
        });
    }

    async onBlur(ev) {
        if (this.isReadonly) return;
        
        const rawValue = ev.target.value;
        const parsed = this.parse(rawValue);
        
        await this.props.record.update({ 
            [this.props.name]: parsed 
        });
        
        if (this.inputRef.el) {
            this.inputRef.el.value = this.formattedValue;
        }
    }

    onKeydown(ev) {
        if (this.isReadonly) return;
        
        const allowedKeys = [
            "Backspace", "Delete", "ArrowLeft", "ArrowRight",
            "ArrowUp", "ArrowDown", "Home", "End", "Tab", "Enter", "Escape",
        ];
        
        if (allowedKeys.includes(ev.key)) {
            if (ev.key === "Enter") {
                ev.target.blur();  
            }
            return;
        }
        
        const allowedChars = /[0-9.,%-]/;
        if (!allowedChars.test(ev.key)) {
            ev.preventDefault();
        }
    }
}

registry.category("fields").add("null_float", {
    component: NullFloatField,
    supportedTypes: ["float", "integer", "monetary"],
});