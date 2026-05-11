odoo.define('sh_backmate_theme_adv.menu', function (require) {
    "use strict";


    var core = require('web.core');
    var AppsMenu = require("web.AppsMenu");
    var config = require("web.config");
    var Menu = require("web.Menu");
    var FormRenderer = require('web.FormRenderer');
    var rpc = require("web.rpc");
    
    const BaseSettingRenderer = require('base.settings').Renderer;


    var user = require('web.session');
    var FormController = require('web.FormController');

    FormController.include({
        _onContentClicked(ev) {
            if (this.mode === 'readonly' && user.sh_enable_one_click) {
                this._setMode('edit');
            }
        },

    })
    BaseSettingRenderer.include({


        start: function () {
            var prom = this._super.apply(this, arguments);
            if (config.device.isMobile) {
                core.bus.on("DOM_updated", this, function () {
                    this._moveToTab(this.currentIndex || this._currentAppIndex());
                });
            }
            return prom;
        },

        _activateSettingMobileTab: function (currentTab) {
            var self = this;
            var moveTo = currentTab;
            var next = moveTo + 1;
            var previous = moveTo - 1;

            this.$(".settings .app_settings_block").removeClass("previous next current before after");
            this.$(".settings_tab .tab").removeClass("previous next current before after");
            _.each(this.modules, function (module, index) {
                var tab = self.$(".tab[data-key='" + module.key + "']");
                var view = module.settingView;

                if (index === previous) {
                    tab.addClass("previous");
                    tab.css("margin-left", "0px");
                    view.addClass("previous");
                } else if (index === next) {
                    tab.addClass("next");
                    tab.css("margin-left", "-" + tab.outerWidth() + "px");
                    view.addClass("next");
                } else if (index < moveTo) {
                    tab.addClass("before");
                    tab.css("margin-left", "-" + tab.outerWidth() + "px");
                    view.addClass("before");
                } else if (index === moveTo) {
                    var marginLeft = tab.outerWidth() / 2;
                    tab.css("margin-left", "-" + marginLeft + "px");
                    tab.addClass("current");
                    view.addClass("current");
                } else if (index > moveTo) {
                    tab.addClass("after");
                    tab.css("margin-left", "0");
                    view.addClass("after");
                }
            });
        },

        _moveToTab: function (index) {
            this.currentIndex = !index || index === -1 ? 0 : (index === this.modules.length ? index - 1 : index);
            if (this.currentIndex !== -1) {
                if (this.activeView) {
                    this.activeView.addClass("o_hidden");
                }
                if (this.activeTab) {
                    this.activeTab.removeClass("selected");
                }
                var view = this.modules[this.currentIndex].settingView;
                var tab = this.$(".tab[data-key='" + this.modules[this.currentIndex].key + "']");
                view.removeClass("o_hidden");
                this.activeView = view;
                this.activeTab = tab;
                if (config.device.isMobile) {
                    this._activateSettingMobileTab(this.currentIndex);
                } else {
                    tab.addClass("selected");
                }

            }
        },

    });


    // Responsive view "action" buttons
    FormRenderer.include({
        /**
         * In mobiles, put all statusbar buttons in a dropdown.
         *
         * @override
         */
        _renderHeaderButtons: function () {
            var $buttons = this._super.apply(this, arguments);
            if (
                !config.device.isMobile ||
                !$buttons.is(":has(>:not(.o_invisible_modifier))")
            ) {
                return $buttons;
            }

            // $buttons must be appended by JS because all events are bound
            $buttons.addClass("dropdown-menu");
            var $dropdown = $(core.qweb.render(
                'sh_backmate_theme_adv.MenuStatusbarButtons'
            ));
            $buttons.addClass("dropdown-menu").appendTo($dropdown);
            return $dropdown;
        },
    });


    var RelationalFields = require('web.relational_fields');

    RelationalFields.FieldStatus.include({

        /**
         * Fold all on mobiles.
         *
         * @override
         */
        _setState: function () {
            this._super.apply(this, arguments);
            if (config.device.isMobile) {
                _.map(this.status_information, function (value) {
                    value.fold = true;
                });
            }
        },
    });




    Menu.include({
        events: _.extend({
            // Clicking a hamburger menu item should close the hamburger
            "click .o_menu_sections [role=menuitem]": "_hideMobileSubmenus",
            // Opening any dropdown in the navbar should hide the hamburger
            "show.bs.dropdown .o_menu_systray, .o_menu_apps":
                "_hideMobileSubmenus",
        }, Menu.prototype.events),

        start: function () {
            this.$menu_toggle = this.$(".o-menu-toggle");
            return this._super.apply(this, arguments);
        },
        change_menu_section: function (primary_menu_id) {
            // softhealer ---quick menu start
        
            var sh_url = window.location.href
            if (sh_url) {
                rpc.query({
                    model: 'sh.wqm.quick.menu',
                    method: 'is_quick_menu_avail_url',
                    args: ['', sh_url]
                }).then(function (rec) {
                    if (rec) {
                        $('.o_main_navbar').find('.o_menu_systray').find('.sh_bookmark').addClass('active');
                    }
                    else {
                        $('.o_main_navbar').find('.o_menu_systray').find('.sh_bookmark').removeClass('active');
                    }
    
                });
            }
            else{
                $('.o_main_navbar').find('.o_menu_systray').find('.sh_bookmark').removeClass('active');
            }
            // quick menu end



                    if (!this.$menu_sections[primary_menu_id]) {
                        this._updateMenuBrand();
                        return; // unknown menu_id
                    }
            
                    if (this.current_primary_menu === primary_menu_id) {
                        return; // already in that menu
                    }
            
                    if (this.current_primary_menu) {
                        this.$menu_sections[this.current_primary_menu].detach();
                    }
            
                    // Get back the application name
                    for (var i = 0; i < this.menu_data.children.length; i++) {
                        if (this.menu_data.children[i].id === primary_menu_id) {
                            this._updateMenuBrand(this.menu_data.children[i].name);
                            break;
                        }
                    }
            
                    this.$menu_sections[primary_menu_id].appendTo(this.$section_placeholder);
                    this.current_primary_menu = primary_menu_id;
            
                    core.bus.trigger('resize');
                },

        /**
         * Hide menus for current app if you're in mobile
         */
        _hideMobileSubmenus: function () {
            if (
                this.$menu_toggle.is(":visible") &&
                this.$section_placeholder.is(":visible")
            ) {
                this.$section_placeholder.collapse("hide");
            }
        },

        /**
         * No menu brand in mobiles
         *
         * @override
         */
        _updateMenuBrand: function () {
            if (!config.device.isMobile) {
                return this._super.apply(this, arguments);
            }
        },
    });









});
