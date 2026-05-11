odoo.define('npd_signature.text_signature', function (require) {
"use strict";

var FormController = require('web.FormController');
var core = require('web.core');

var _t = core._t;

// Default font for text signature
var DEFAULT_FONT = "Pacifico";
var DEFAULT_COLOR = "#000080";
var DEFAULT_SIZE = 48;

// Google Fonts URL
var GOOGLE_FONTS_URL = 'https://fonts.googleapis.com/css2?family=Pacifico&display=swap';

// Load Google Fonts
var fontsLoaded = false;
function loadGoogleFonts() {
    if (fontsLoaded) return Promise.resolve();
    return new Promise(function(resolve) {
        var link = document.createElement('link');
        link.href = GOOGLE_FONTS_URL;
        link.rel = 'stylesheet';
        link.onload = function() {
            fontsLoaded = true;
            setTimeout(resolve, 500);
        };
        link.onerror = function() {
            console.warn('Failed to load Google Fonts');
            fontsLoaded = true;
            resolve();
        };
        document.head.appendChild(link);
    });
}

// Load fonts on module init
loadGoogleFonts();

/**
 * Generate signature image from text (ใช้ชื่อลายเซ็นเป็นข้อความ)
 */
function generateTextSignatureImage(text) {
    return new Promise(function(resolve, reject) {
        if (!text) {
            resolve(null);
            return;
        }

        // Create canvas
        var canvas = document.createElement('canvas');
        var ctx = canvas.getContext('2d');

        // Set font first to measure text
        ctx.font = DEFAULT_SIZE + 'px "' + DEFAULT_FONT + '", cursive';
        var textMetrics = ctx.measureText(text);
        
        // Set canvas size with padding
        var padding = 30;
        canvas.width = Math.ceil(textMetrics.width) + (padding * 2);
        canvas.height = Math.ceil(DEFAULT_SIZE * 1.5) + (padding * 2);
        
        // Clear with transparent background
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw text
        ctx.font = DEFAULT_SIZE + 'px "' + DEFAULT_FONT + '", cursive';
        ctx.fillStyle = DEFAULT_COLOR;
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'center';
        ctx.fillText(text, canvas.width / 2, canvas.height / 2);
        
        // Convert to base64 (PNG with transparency)
        try {
            var imageData = canvas.toDataURL('image/png');
            var base64Data = imageData.split(',')[1];
            resolve(base64Data);
        } catch (e) {
            reject(e);
        }
    });
}

// Extend FormController to handle text signature generation
FormController.include({
    
    /**
     * Override saveRecord to generate text signature before saving
     * ใช้ค่าจาก name field เป็นข้อความลายเซ็น
     */
    saveRecord: function (recordID) {
        var self = this;
        var record = this.model.get(recordID || this.handle);
        
        // Check if this is npd.signature model with text type
        // ใช้ name เป็นข้อความลายเซ็น
        if (record && record.model === 'npd.signature' && 
            record.data.signature_type === 'text' && 
            record.data.name) {
            
            return loadGoogleFonts().then(function() {
                return generateTextSignatureImage(record.data.name);
            }).then(function(imageData) {
                if (imageData) {
                    // Update the signature_text_image field
                    return self.model.notifyChanges(record.id, {
                        signature_text_image: imageData
                    }).then(function() {
                        return self._super.apply(self, [recordID]);
                    });
                }
                return self._super.apply(self, [recordID]);
            }).catch(function(error) {
                console.error('Error generating text signature:', error);
                return self._super.apply(self, [recordID]);
            });
        }
        
        return this._super.apply(this, arguments);
    },
});

/**
 * เปลี่ยนข้อความ placeholder เป็นภาษาไทย
 */
$(document).ready(function() {
    function translateSignaturePlaceholder() {
        $('svg text').each(function() {
            var text = $(this).text().trim();
            if (text === 'Draw your signature') {
                $(this).text('วาดลายเซ็นของคุณ');
            }
        });
        
        document.querySelectorAll('svg text').forEach(function(el) {
            if (el.textContent.trim() === 'Draw your signature') {
                el.textContent = 'วาดลายเซ็นของคุณ';
            }
        });
    }
    
    translateSignaturePlaceholder();
    setInterval(translateSignaturePlaceholder, 500);
    
    var observer = new MutationObserver(function(mutations) {
        translateSignaturePlaceholder();
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});

return {
    generateTextSignatureImage: generateTextSignatureImage,
    loadGoogleFonts: loadGoogleFonts,
};

});
