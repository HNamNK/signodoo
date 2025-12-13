/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { SignatureDialog } from "@web/core/signature/signature_dialog";
import { useService } from "@web/core/utils/hooks";
import { onMounted } from "@odoo/owl";

export class BulkSignWizardController extends FormController {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
        
        onMounted(() => {
            this.openSignatureDialog();
        });
    }

    openSignatureDialog() {
        const defaultName = this.model.root.data.signature_name || '';
        
        this.dialog.add(SignatureDialog, {
            defaultName: defaultName,
            uploadSignature: (signatureData) => {
                console.log("Captured signature:", signatureData);
                this.model.root.update({
                    signature_name: signatureData.name,
                    signature_image: signatureData.signatureImage
                });
            },
        });
    }
}

registry.category("views").add("bulk_sign_wizard_form", {
    ...formView,
    Controller: BulkSignWizardController,
});