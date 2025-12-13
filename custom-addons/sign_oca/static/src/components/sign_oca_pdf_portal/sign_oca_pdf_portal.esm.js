/** @odoo-module **/
/* global window */

import {App, useRef, whenReady} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {makeEnv, startServices} from "@web/env";
import SignOcaPdf from "../sign_oca_pdf/sign_oca_pdf.esm.js";
import {getTemplate} from "@web/core/templates";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {rpc} from "@web/core/network/rpc";

export class SignOcaPdfPortal extends SignOcaPdf {
    setup() {
        this.rpc = rpc;
        this.signOcaFooter = useRef("sign_oca_footer");
        this.signer_id = this.props.signer_id;
        this.access_token = this.props.access_token;
        
        // 🔥 TRACK render state để tránh duplicate
        this._isRendering = false;
        this._fieldsRendered = false;
        
        super.setup(...arguments);
    }

    async willStart() {
        console.log('🔍 [Portal] willStart called');
        this.info = await this.rpc(
            "/sign_oca/info/" + this.signer_id + "/" + this.access_token
        );
        console.log('🔍 [Portal] Info received:', this.info);
        console.log('🔍 [Portal] to_sign from backend:', this.info.to_sign);
    }

    getPdfUrl() {
        return "/sign_oca/content/" + this.signer_id + "/" + this.access_token;
    }

    checkToSign() {
        console.log('🔍 [Portal] checkToSign called');
        console.log('🔍 [Portal] this.to_sign_update:', this.to_sign_update);
        
        this.to_sign = this.to_sign_update;
        
        console.log('🔍 [Portal] Final this.to_sign:', this.to_sign);
        console.log('🔍 [Portal] Footer element:', this.signOcaFooter.el);
        
        if (this.to_sign_update) {
            console.log('✅ [Portal] Showing footer button');
            $(this.signOcaFooter.el).show();
        } else {
            console.log('❌ [Portal] Hiding footer button');
            $(this.signOcaFooter.el).hide();
        }
    }

    // 🔥 REFACTOR: Tách biệt render và validation logic
    postIframeFields() {
        console.log('[Portal] postIframeFields called, rendered:', this._fieldsRendered);
        
        // 🔥 Chỉ render một lần duy nhất
        if (this._fieldsRendered || this._isRendering) {
            console.log('[Portal] Skip duplicate render');
            this._postRenderValidation();
            return;
        }

        this._isRendering = true;
        
        try {
            // 🔥 Sử dụng parent logic chuẩn - KHÔNG override
            super.postIframeFields(...arguments);
            this._fieldsRendered = true;
            
            // 🔥 Chạy validation RIÊNG BIỆT sau khi render xong
            this._postRenderValidation();
            
        } finally {
            this._isRendering = false;
        }
    }

    // 🔥 SEPARATE: Logic validation riêng biệt
    _postRenderValidation() {
        console.log('[Portal] Running post-render validation');
        
        // Portal-specific validation logic
        this.checkFilledAll();
        
        // 🔥 Setup portal-specific event handlers
        this._setupPortalHandlers();
    }

    // 🔥 CLEAN: Portal-specific handlers
    _setupPortalHandlers() {
        // Chỉ setup các handler đặc thù của Portal
        // Không can thiệp vào render logic
        Object.values(this.items).forEach(item => {
            // Portal-specific interaction handlers nếu cần
            if (item.dataset && item.dataset.fieldType === 'signature') {
                // Special handling for signature fields in portal
            }
        });
    }

    _renderFieldContent(item, signatureItem) {
        console.log(`🔍 [Portal] _renderFieldContent called for: ${item.name}, type: ${item.field_type}`);
        
        // Check if already rendered
        if (signatureItem[0].children.length > 0) {
            console.log(`🔍 [Portal] Field ${item.name} already has content, skip render`);
            return;
        }

        // Call parent render
        super._renderFieldContent(item, signatureItem);
        
        // Portal-specific enhancements
        this._enhancePortalField(item, signatureItem);
        
        console.log(`✅ [Portal] Field ${item.name} rendered successfully`);
    }
    // 🔥 ENHANCEMENT: Portal-specific field improvements
    _enhancePortalField(item, signatureItem) {
        // Chỉ enhance UI/UX, không thay đổi render logic
        const fieldElement = signatureItem[0].querySelector('input, div');
        if (fieldElement && item.field_type === 'auto_fill') {
            // Portal-specific styling
            fieldElement.style.fontStyle = 'italic';
            fieldElement.title = `Portal view: ${fieldElement.title || item.name}`;
        }
    }

    checkFilledAll() {
        console.log('🔍 [Portal] checkFilledAll called');
        console.log('🔍 [Portal] this.info?.items:', Object.keys(this.info?.items || {}));
        
        // 🔥 KIỂM TRA: Logic validation có đúng không?
        let allFilled = true;
        const requiredFields = [];
        
        Object.values(this.info?.items || {}).forEach(item => {
            console.log(`🔍 [Portal] Field ${item.name}: required=${item.required}, role_id=${item.role_id}, current_role=${this.info.role_id}, value="${item.value}"`);
            
            if (item.required && item.role_id === this.info.role_id) {
                requiredFields.push(item);
                if (!item.value) {
                    allFilled = false;
                    console.log(`❌ [Portal] Required field not filled: ${item.name}`);
                }
            }
        });

        console.log('🔍 [Portal] Required fields:', requiredFields.length);
        console.log('🔍 [Portal] All required filled:', allFilled);
        
        this.to_sign_update = allFilled;
        console.log('🔍 [Portal] Setting to_sign_update to:', this.to_sign_update);
        
        this.checkToSign();
    }

    // 🔥 MAINTAIN: Signing logic giữ nguyên để không ảnh hưởng workflow
    async _onClickSign(ev) {
        ev.target.disabled = true;
        const position = await this.getLocation();
        
        console.log('[Portal] Signing with data:', {
            items: Object.keys(this.info.items || {}),
            hasLocation: !!position
        });
        
        this.rpc("/sign_oca/sign/" + this.signer_id + "/" + this.access_token, {
            items: this.info.items,
            latitude: position && position.coords && position.coords.latitude,
            longitude: position && position.coords && position.coords.longitude,
        }).then((action) => {
            // Giữ nguyên logic redirect
            if (action.type === "ir.actions.act_url") {
                window.location = action.url;
            } else {
                window.location.reload();
            }
        });
    }

    // 🔥 HELPER: Debug info
    _debugPortalState() {
        console.log('[Portal Debug]', {
            fieldsRendered: this._fieldsRendered,
            isRendering: this._isRendering,
            itemCount: Object.keys(this.items || {}).length,
            infoItems: Object.keys(this.info?.items || {}),
            toSign: this.to_sign_update
        });
    }
}

SignOcaPdfPortal.template = "sign_oca.SignOcaPdfPortal";
SignOcaPdfPortal.props = {
    access_token: String,
    signer_id: Number,
};
SignOcaPdfPortal.components = {MainComponentsContainer};

export async function initDocumentToSign(document, sign_oca_backend_info) {
    const env = makeEnv();
    await startServices(env);
    await whenReady();
    const app = new App(SignOcaPdfPortal, {
        getTemplate,
        env: env,
        dev: env.debug,
        props: {
            access_token: sign_oca_backend_info.access_token,
            signer_id: sign_oca_backend_info.signer_id,
        },
        translateFn: _t,
        translatableAttributes: ["data-tooltip"],
    });
    await app.mount(document.body);
}

export default {SignOcaPdfPortal, initDocumentToSign};