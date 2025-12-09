

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

export class EmployeeContractListController extends ListController {
    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        
        this.buttonContainer = null;

        onMounted(() => {
            
            setTimeout(() => {
                this.addCustomButtons();
            }, 100);
        });

        onPatched(() => {
            
            this.updateCustomButtons();
        });

        
        onWillUnmount(() => {
            
            this.removeCustomButtons();
        });
    }

        removeCustomButtons() {
        
        const allButtons = document.querySelectorAll('.o_contract_custom_buttons');
        allButtons.forEach(btn => {
            
            btn.remove();
        });
        
        
        this.buttonContainer = null;
    }

        getActionType() {
        const actionType = this.props.context?.default_action_type 
                        || this.env.searchModel?.context?.default_action_type
                        || this.model?.config?.context?.default_action_type
                        || this.props.globalState?.context?.default_action_type;
        
        
        
        if (!actionType) {
            const domain = this.props.domain || this.model?.root?.domain || [];
            
            
            const isCreateView = domain.some(d => 
                Array.isArray(d) && d[0] === 'contract_ids' && d[1] === '=' && d[2] === false
            );
            
            const isRegenerateView = domain.some(d => 
                Array.isArray(d) && d[0] === 'contract_ids' && d[1] === '!=' && d[2] === false
            );
            
            
            
            if (isCreateView) return 'create';
            if (isRegenerateView) return 'regenerate';
        }
        
        return actionType;
    }

        addCustomButtons() {
        
        
        
        this.removeCustomButtons();
        
        const pager = document.querySelector('.o_cp_pager');
        if (!pager) {
            console.warn('[Contract Buttons] Pager not found, retrying...');
            setTimeout(() => this.addCustomButtons(), 200);
            return;
        }

        

        const actionType = this.getActionType();
        if (!actionType) {
            console.warn('[Contract Buttons] No action_type found, skipping buttons');
            return;
        }

        
        this.buttonContainer = document.createElement('div');
        this.buttonContainer.className = 'o_contract_custom_buttons me-2 d-inline-flex gap-2';
        this.buttonContainer.style.display = 'none';
        this.buttonContainer.dataset.actionType = actionType; 

        if (actionType === 'create') {
            const createBtn = document.createElement('button');
            createBtn.className = 'btn btn-primary';
            createBtn.innerHTML = `
                <i class="fa fa-file-text-o me-1"></i>
                <span>Tạo Hợp Đồng</span>
                <span class="badge bg-white text-primary ms-1 contract-count">0</span>
            `;
            createBtn.title = 'Tạo hợp đồng hàng loạt cho nhân viên đã chọn';
            createBtn.onclick = () => this.onCreateContractsClick();
            this.buttonContainer.appendChild(createBtn);
            
            
        } else if (actionType === 'regenerate') {
            const regenerateBtn = document.createElement('button');
            regenerateBtn.className = 'btn btn-success';
            regenerateBtn.innerHTML = `
                <i class="fa fa-refresh me-1"></i>
                <span>Tái Tạo Hợp Đồng</span>
                <span class="badge bg-white text-success ms-1 contract-count">0</span>
            `;
            regenerateBtn.title = 'Tái tạo hợp đồng hàng loạt cho nhân viên đã chọn';
            regenerateBtn.onclick = () => this.onRegenerateContractsClick();
            this.buttonContainer.appendChild(regenerateBtn);
            
            
        } else {
            console.warn('[Contract Buttons] Unknown action_type:', actionType);
            return;
        }

        pager.parentNode.insertBefore(this.buttonContainer, pager);
        

        this.updateCustomButtons();
    }

        updateCustomButtons() {
        
        if (!this.buttonContainer || !this.buttonContainer.isConnected) {
            
            return;
        }

        const selectedCount = this.getSelectedIds().length;
        const countBadges = this.buttonContainer.querySelectorAll('.contract-count');

        

        if (selectedCount > 0) {
            this.buttonContainer.style.display = 'inline-flex';
            countBadges.forEach(badge => {
                badge.textContent = selectedCount;
            });
        } else {
            this.buttonContainer.style.display = 'none';
        }
    }

        getSelectedIds() {
        const selection = this.model?.root?.selection 
                       || this.model?.root?.records?.filter(r => r.selected)
                       || [];
        
        if (Array.isArray(selection)) {
            return selection.map(record => record.resId || record.id);
        }
        
        return [];
    }

        async onCreateContractsClick() {
        const selectedIds = this.getSelectedIds();

        

        if (selectedIds.length === 0) {
            this.notification.add("Vui lòng chọn ít nhất một nhân viên để tạo hợp đồng.", {
                type: "warning",
            });
            return;
        }

        try {
            const result = await this.orm.call(
                "hr.employee",
                "action_open_contract_create_wizard_from_selection",
                [selectedIds],
                {}
            );

            

            if (result) {
                await this.action.doAction(result);
            }
        } catch (error) {
            console.error('[Contract Buttons] Create error:', error);
            this.notification.add(error.message || "Có lỗi xảy ra khi tạo hợp đồng.", {
                type: "danger",
            });
        }
    }

        async onRegenerateContractsClick() {
        const selectedIds = this.getSelectedIds();

        

        if (selectedIds.length === 0) {
            this.notification.add("Vui lòng chọn ít nhất một nhân viên để tái tạo hợp đồng.", {
                type: "warning",
            });
            return;
        }

        try {
            const result = await this.orm.call(
                "hr.employee",
                "action_open_contract_regenerate_wizard_from_selection",
                [selectedIds],
                {}
            );

            

            if (result) {
                await this.action.doAction(result);
            }
        } catch (error) {
            console.error('[Contract Buttons] Regenerate error:', error);
            this.notification.add(error.message || "Có lỗi xảy ra khi tái tạo hợp đồng.", {
                type: "danger",
            });
        }
    }
}

export const employeeContractListView = {
    ...listView,
    Controller: EmployeeContractListController,
};

registry.category("views").add("employee_contract_list", employeeContractListView);