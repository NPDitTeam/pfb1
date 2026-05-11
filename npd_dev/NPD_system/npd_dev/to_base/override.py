from odoo import http

db_filter_core = http.db_filter


def db_filter(dbs, httprequest=None):
    dbs = db_filter_core(dbs, httprequest)
    httprequest = httprequest or http.request.httprequest
    custom_odoo_dbfilter = httprequest.environ.get('HTTP_X_ODOO_DBFILTER')
    if custom_odoo_dbfilter:
        return [custom_odoo_dbfilter]
    return dbs


http.db_filter = db_filter
