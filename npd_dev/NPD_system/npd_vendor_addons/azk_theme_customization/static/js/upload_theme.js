odoo.define("azk_theme_customization.ribbon", function(require) {
    "use strict";

    var rpc = require("web.rpc");
    var core = require("web.core");
    var session = require('web.session');
    
    core.bus.on("DOM_updated", null, function() {    	
	    rpc.query({	
                model: 'res.company',	
                method: 'rpc_ifo_theme',	
                args: [[parseInt(session.user_context.allowed_company_ids[0])]],	
            })	
            .then(function (data) {
				
            	if (data.length > 0){
					var head  = document.getElementsByTagName('head')[0];
						
					if(!document.getElementById('azk_theme_link_css')){
						var link  = document.createElement('link');
						link.id   = 'azk_theme_link_css';
						link.rel  = 'stylesheet';
						link.type = 'text/css';
						link.href = data[0]['link_href_css'];
						head.appendChild(link);
					}
					
					if(!document.getElementById('azk_theme_script_js') && data[0]['script_src_js']){
						var script  = document.createElement('script');
						script.id   = 'azk_theme_script_js';
						script.type = 'text/javascript';
						script.src = data[0]['script_src_js'];
						head.appendChild(script);
					}
	            	if (data.length > 1 && !document.getElementById('azk_theme_ribbon'))
	            		{
		    	    		var ribbon = $('<div id="azk_theme_ribbon" class="theme-ribbon">' + data[1]['ribbon_text'] + '</div>');	
		    	            $("body").append(ribbon);
	            		}
            	}  	
        });        
    });
});
