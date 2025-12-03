/** @odoo-module **/

import { registry } from "@web/core/registry";

const hideContractMenuService = {
    start() {
        const hideMenu = () => {
            // Ẩn menu với XML ID đúng
            const menuItems = document.querySelectorAll('[data-menu-xmlid="hr_contract.hr_menu_contract"]');
            
            menuItems.forEach(item => {
                const li = item.closest('li');
                if (li) {
                    li.style.display = 'none';
                    console.log('✓ Hidden menu: hr_contract.hr_menu_contract');
                } else {
                    // Nếu item chính là <li>
                    item.style.display = 'none';
                    console.log('✓ Hidden menu item directly');
                }
            });
        };

        // Chạy nhiều lần
        setTimeout(hideMenu, 100);
        setTimeout(hideMenu, 300);
        setTimeout(hideMenu, 600);

        // Observer
        const observer = new MutationObserver(hideMenu);
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    },
};

registry.category("services").add("hide_contract_menu", hideContractMenuService);