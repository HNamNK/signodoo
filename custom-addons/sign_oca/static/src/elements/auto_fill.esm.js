/** @odoo-module **/
import { registry } from "@web/core/registry";

const autoFillSignOca = {
    change(value, parent, item) {
        // auto_fill là readonly → không làm gì
        return;
    },

    createContent(item) {
        const el = document.createElement("div");
        el.classList.add("o_sign_oca_field");

        const displayText = item.value || item.default_value || item.name || "Auto-fill";
        el.textContent = String(displayText);

        el.style.pointerEvents = "none";
        el.setAttribute("data-readonly", "1");
        return el;
    },


    generate(parent, item, signatureItem) {
        // Nếu backend đã render thì không overlay nữa
        return null;
    },

    check(item) {
        // auto_fill luôn hợp lệ ở frontend (readonly)
        return true;
    },
};

registry.category("sign_oca").add("auto_fill", autoFillSignOca);
