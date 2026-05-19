# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class MapController(http.Controller):

    # NOTE: ปุ่มเปิดแผนที่เปลี่ยนไปใช้ PHP ภายนอก (npdhrms.com/checkin_map.php) แล้ว
    #   เพื่อเลี่ยงปัญหา Odoo website ใส่ /th/ prefix → 404
    # route นี้เก็บไว้เป็น fallback เฉย ๆ (ไม่มีปุ่มเรียกแล้ว) — single path กัน shadow
    @http.route('/web/checkin_map/<int:record_id>',
                type='http', auth='public', website=False)
    def checkin_map(self, record_id, **kwargs):
        record = request.env['hr.checkin.distance'].sudo().browse(record_id)
        if not record.exists():
            return request.not_found()

        lat = float(record.latitude or '13.7563')
        lng = float(record.longitude or '100.5018')
        distance = int(record.distance_meter or '100')
        branch = record.branch_id.name if record.branch_id else 'ไม่ระบุสาขา'

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>html,body,#map{{height:100%;margin:0;padding:0;}}</style>
</head>
<body>
    <div id="map"></div>
    <script>
    function initMap(){{
        var c={{lat:{lat},lng:{lng}}};
        var map=new google.maps.Map(document.getElementById("map"),{{zoom:17,center:c}});
        new google.maps.Marker({{position:c,map:map,title:"{branch}"}});
        new google.maps.Circle({{
            strokeColor:"#007bff",strokeOpacity:0.8,strokeWeight:2,
            fillColor:"#007bff",fillOpacity:0.15,
            map:map,center:c,radius:{distance}
        }});
    }}
    </script>
    <script src="https://maps.googleapis.com/maps/api/js?key=AIzaSyCHKkMOyDdI29v52SULcRx_OcB3i-MD7lw&callback=initMap" async defer></script>
</body>
</html>"""
        return request.make_response(html, headers=[('Content-Type', 'text/html')])
