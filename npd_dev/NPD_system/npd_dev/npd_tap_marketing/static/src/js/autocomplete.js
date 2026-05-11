odoo.define('pfb_npd_tap_shipment_information.autocomplete_location', function (require) {
    "use strict";

    var fieldRegistry = require('web.field_registry');
    var basicFields = require('web.basic_fields');

    var AutocompleteLocation = basicFields.FieldChar.extend({
        start: function () {
            console.log("🔹 AutocompleteLocation Widget Loaded");
            this._super.apply(this, arguments);
            this._startAutocomplete();
        },

        _startAutocomplete: function () {
            var self = this;

            function waitForElement(selector, callback) {
                var checkExist = setInterval(function () {
                    var inputField = $(selector);
                    if (inputField.length) {
                        clearInterval(checkExist);
                        callback(inputField);
                    }
                }, 500);
            }

            waitForElement("input[name='pickup_location']", function (inputField) {
                console.log("✅ Autocomplete field found:", inputField);
                self._enableAutocomplete(inputField);
            });

            waitForElement("input[name='destination']", function (inputField) {
                console.log("✅ Destination field found:", inputField);
                self._enableAutocomplete(inputField);
            });
        },

        _enableAutocomplete: function (inputField) {
            var self = this;

            if (!inputField || !inputField.length) {
                console.error("❌ Input field not found");
                return;
            }

            console.log("🔹 Initializing Google Autocomplete for:", inputField);

            var autocomplete = new google.maps.places.Autocomplete(inputField[0], {
                componentRestrictions: { country: "th" },
                types: ["geocode"]
            });

            autocomplete.addListener('place_changed', function () {
                var place = autocomplete.getPlace();
                if (!place.formatted_address) {
                    console.warn("⚠️ No formatted address found");
                    return;
                }

                console.log("✅ Selected Address:", place.formatted_address);
                inputField.val(place.formatted_address).trigger('change');

                // คำนวณระยะทางเมื่อเลือกจุดหมายปลายทาง
                var pickupField = $("input[name='pickup_location']").val();
                var destinationField = $("input[name='destination']").val();
                if (pickupField && destinationField) {
                    self._calculateDistance(pickupField, destinationField);
                }
            }.bind(this));
        },

        _calculateDistance: function (pickup, destination) {
            console.log("🚗 Calculating distance from:", pickup, "to", destination);

            var apiKey = "AIzaSyCHKkMOyDdI29v52SULcRx_OcB3i-MD7lw"; // 🔥 ใช้ API Key ของคุณ
            var url = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix";

            var payload = {
                origins: [{ waypoint: { address: pickup } }],
                destinations: [{ waypoint: { address: destination } }],
                travelMode: "DRIVE"
            };

            fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": apiKey,
                    "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters,duration"
                },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => {
                console.log("✅ Routes API Response:", data);

                if (data.length > 0 && data[0].distanceMeters) {
                    var distance = data[0].distanceMeters / 1000; // แปลงเมตรเป็นกิโลเมตร
                    console.log("✅ Distance calculated:", distance, "km");

                    // อัปเดตค่าในฟอร์ม Odoo
                    $("input[name='distance_km']").val(distance).trigger('change');
                } else {
                    console.error("❌ No valid distance found in API response");
                }
            })
            .catch(error => console.error("Google Routes API Error:", error));
        }
    });

    fieldRegistry.add('autocomplete_location', AutocompleteLocation);
});
