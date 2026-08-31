odoo.define('npd_ai_it_assistant/static/src/components/messaging_menu/messaging_menu.js', function (require) {
'use strict';

/**
 * เพิ่มแท็บ "ตัวช่วย AI-IT" เข้าไปในเมนูสนทนา (ข้าง ๆ ทั้งหมด / สนทนา / ช่องทาง)
 *
 * แท็บนี้ไม่ได้แสดงรายการห้องแชท แต่แสดง "หัวข้อปัญหา" ที่ให้ AI ช่วยแก้ได้
 * เมื่อกดหัวข้อ ระบบจะเปิดห้องแชทกับ "ตัวช่วย AI-IT" ให้อัตโนมัติ
 */

const components = {
    MessagingMenu: require('mail/static/src/components/messaging_menu/messaging_menu.js'),
};

const { useState } = owl.hooks;

const AI_IT_TAB_ID = 'ai_it';

components.MessagingMenu.patch('npd_ai_it_assistant/static/src/components/messaging_menu/messaging_menu.js', T =>
    class extends T {

        /**
         * @override
         */
        _constructor(...args) {
            super._constructor(...args);
            this.aiIt = useState({
                topics: [],
                isLoading: false,
                isLoaded: false,
            });
            // กัน setState หลังคอมโพเนนต์ถูกทำลาย (ผู้ใช้ปิดเมนูระหว่างรอ RPC)
            this._aiItIsAlive = true;
        }

        /**
         * @override
         */
        willUnmount() {
            this._aiItIsAlive = false;
            super.willUnmount();
        }

        /**
         * @override
         */
        mounted() {
            super.mounted();
            if (this.messagingMenu && this.messagingMenu.activeTabId === AI_IT_TAB_ID) {
                this._loadAiItTopics();
            }
        }

        //----------------------------------------------------------------------
        // Public
        //----------------------------------------------------------------------

        /**
         * @returns {string}
         */
        get aiItTabId() {
            return AI_IT_TAB_ID;
        }

        /**
         * @returns {string}
         */
        get aiItTabLabel() {
            return this.env._t("ตัวช่วย AI-IT");
        }

        /**
         * เพิ่มแท็บให้ navbar ตอนใช้งานบนมือถือด้วย
         *
         * @override
         * @returns {Object[]}
         */
        get tabs() {
            return super.tabs.concat([{
                icon: 'fa fa-magic',
                id: AI_IT_TAB_ID,
                label: this.aiItTabLabel,
            }]);
        }

        //----------------------------------------------------------------------
        // Private
        //----------------------------------------------------------------------

        /**
         * ดึงรายการหัวข้อจากเซิร์ฟเวอร์ (โหลดครั้งเดียวต่อการเปิดเมนูหนึ่งครั้ง)
         *
         * @private
         */
        async _loadAiItTopics() {
            if (this.aiIt.isLoading || this.aiIt.isLoaded) {
                return;
            }
            this.aiIt.isLoading = true;
            let topics = [];
            try {
                topics = await this.env.services.rpc({
                    model: 'npd.ai.it.topic',
                    method: 'get_available_topics',
                    args: [],
                }, { shadow: true });
            } catch (error) {
                if (this._aiItIsAlive) {
                    this.aiIt.isLoading = false;
                }
                throw error;
            }
            if (!this._aiItIsAlive) {
                return;
            }
            this.aiIt.topics = topics || [];
            this.aiIt.isLoading = false;
            this.aiIt.isLoaded = true;
        }

        //----------------------------------------------------------------------
        // Handlers
        //----------------------------------------------------------------------

        /**
         * @override
         */
        _onClickDesktopTabButton(ev) {
            super._onClickDesktopTabButton(ev);
            if (ev.currentTarget.dataset.tabId === AI_IT_TAB_ID) {
                this._loadAiItTopics();
            }
        }

        /**
         * @override
         */
        _onSelectMobileNavbarTab(ev) {
            const tabId = ev.detail.tabId;
            super._onSelectMobileNavbarTab(ev);
            if (tabId === AI_IT_TAB_ID) {
                this._loadAiItTopics();
            }
        }

        /**
         * เลือกหัวข้อ -> เปิดห้องแชทกับตัวช่วย AI-IT
         *
         * @private
         * @param {MouseEvent} ev
         */
        async _onClickAiItTopic(ev) {
            const topicId = parseInt(ev.currentTarget.dataset.topicId, 10);
            if (!topicId) {
                return;
            }
            const result = await this.env.services.rpc({
                model: 'npd.ai.it.session',
                method: 'action_start_topic',
                args: [topicId],
            });
            if (!result || result.error) {
                this.env.services['notification'].notify({
                    message: (result && result.error) || this.env._t("เปิดหัวข้อไม่สำเร็จ"),
                    type: 'danger',
                });
                return;
            }
            this.messagingMenu.close();

            // เปิด "ห้องแชท" ตรง ๆ ไม่ใช่ openChat({partnerId})
            // เพราะ mail.partner.getChat() ปฏิเสธ partner ที่ไม่มี res.users
            // ด้วยข้อความ "You can only chat with partners that have a dedicated user."
            // ส่วนบอทของเราจงใจไม่มี user (ไม่ต้องล็อกอิน ไม่ต้องมีสิทธิ์)
            const Thread = this.env.models['mail.thread'];
            const thread = Thread.insert(Object.assign(
                { model: 'mail.channel' },
                Thread.convertData(result.channel_info)
            ));
            thread.open();
        }

    }
);

});
