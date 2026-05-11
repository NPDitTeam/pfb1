odoo.define('sh_backmate_theme_adv.zoomwidget', function (require) {
	"use strict";

	var core = require('web.core');
	var Dialog = require('web.Dialog');
	var Widget = require('web.Widget');
	var rpc = require('web.rpc');
	var SystrayMenu = require('web.SystrayMenu');
	var session = require('web.session');
	var _t = core._t;
	var QWeb = core.qweb;
	var UserMenu = require('web.UserMenu');

	var ZoomWidget = Widget.extend({
		template: "ZoomWidget",
		events: {
			'click .sh_dec': 'setDecZoom', 
			'click .sh_inc': 'setIncZoom', 
			'click .sh_reset': 'setResetZoom', 
		},
		init: function () {
			this._super.apply(this, arguments);
			var self = this;
		},
		setResetZoom: function () {
			var zoom = $('.sh_full').text().split('%')
			if($('.o_content')[0]){
				$($('.o_content')[0].firstChild).removeClass("sh_zoom_"+zoom[0])
				zoom = 100
				$('.sh_full').text(zoom.toString()+'%');
				$($('.o_content')[0].firstChild).addClass("sh_zoom_"+zoom)
			}
			
		},
		setDecZoom: function () {
			var zoom = $('.sh_full').text().split('%')
			if(parseInt(zoom[0])-10 >= 20 && parseInt(zoom[0])-10 <= 200){
				if($('.o_content')[0]){

					$($('.o_content')[0].firstChild).removeClass("sh_zoom_"+zoom[0])
					zoom = parseInt(zoom[0])-10
					$('.sh_full').text(zoom.toString()+'%');
					$($('.o_content')[0].firstChild).addClass("sh_zoom_"+zoom)
				}
			}
			
		},
		setIncZoom: function () {
			var zoom = $('.sh_full').text().split('%')
			if(parseInt(zoom[0])+10 >= 20 && parseInt(zoom[0])+10 <= 200){
				if($('.o_content')[0]){
					$($('.o_content')[0].firstChild).removeClass("sh_zoom_"+zoom[0])
					zoom = parseInt(zoom[0])+10
					$('.sh_full').text(zoom.toString()+'%');
					$($('.o_content')[0].firstChild).addClass("sh_zoom_"+zoom)
				}
			}
		   
		}
	});

	ZoomWidget.prototype.sequence = 10;

	rpc.query({
		model: 'res.users',
		method: 'search_read',
		fields: ['sh_enable_zoom'],
		domain: [['id', '=', session.uid]]
	}, { async: false }).then(function (data) {
		if (data) {
			_.each(data, function (user) {
				if (user.sh_enable_zoom) {
					SystrayMenu.Items.push(ZoomWidget);

				}
			});

		}
	});

	return {
		ZoomWidget: ZoomWidget,
	};
});
