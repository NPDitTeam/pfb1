# -*- coding: utf-8 -*-

from odoo import api, fields, models,_
from odoo.exceptions import UserError, ValidationError
import io
from io import BytesIO,StringIO
import xlrd
import base64
import codecs
import csv
import urllib.request
import sys
import xlsxwriter
import logging
_logger = logging.getLogger(__name__)

try:
    import xlrd
except ImportError:
    _logger.debug('Cannot `import xlrd`.')

try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')


class ImportProductVarient(models.TransientModel):
    _name="import.product"
    _description="import product varient"

    file_type= fields.Selection([("csv","CSV File"),("excel","Excel File")],string="Import File Type",default="csv")
    method= fields.Selection([("with_var","Create Product Variant"),("update_var","Create or Update Product Variants")],string="Method",default="with_var")
    importing_file = fields.Binary('Upload File')
    file_name = fields.Char('File Name')
    file=fields.Binary("Download File")
    sample_file_name=fields.Char('Sample File')

   
    def apply_button(self):
        if not self.importing_file:
            raise UserError(_('Please upload valid csv or xls file...!'))
        if self.file_type == 'excel':
            file_name = str(self.file_name)
            if self.importing_file:
                if '.' not in file_name:
                    raise UserError(_('Please upload valid xls...!'))
                extension = file_name.split('.')[1]
                if extension not in ['xls','xlsx','XLS','XLSX']:
                    raise UserError(_('Please upload only xls file.!'))
               

            inputx = BytesIO()
            inputx.write(base64.decodestring(self.importing_file))
            book = xlrd.open_workbook(file_contents = inputx.getvalue())
            sheet = book.sheet_by_index(0)

            product_dict = {};categ_id_val=1;
            lst=[];attr_dict={};attribute_dict={};main_product_list=[]
            for suits in range(1,sheet.nrows):

                product=sheet.cell(suits, 0).value
                if not product:
                    raise UserError(_("Product Name is missing !!"))


                category_list=[]
                for ids in self.env["product.category"].search([]):
                    category_list.append(ids.name)                

                categ_id=sheet.cell(suits, 4).value.strip()
                if categ_id:
                    categ_str_list=categ_id.split('/')
                    if len(categ_str_list) == 1:
                        if categ_str_list[0].strip() in set(category_list):
                            categ_id_val = self.env['product.category'].search([('name','=',categ_str_list[0].strip())],limit=1).id
                        else:
                            categ_id_val = self.env['product.category'].create({
                                'name':categ_str_list[0].strip(),
                                'parent_id':False,
                                'display_name':categ_id
                            }).id

                    elif len(categ_str_list) == 2:
                        if categ_str_list[-1].strip() in set(category_list):
                            if categ_str_list[0].strip() not in set(category_list):
                                
                                parent_object = self.env["product.category"].create({
                                                    'name':categ_str_list[0].strip(),
                                                    'parent_id':False,
                                                    'display_name':categ_str_list[0].strip()
                                                }).id
                                categ_id_val = self.env['product.category'].create({
                                                    'name':categ_str_list[-1].strip(),
                                                    'parent_id':parent_object,
                                                    'display_name':categ_id
                                                }).id
                            else:
                                categ_id_val = self.env['product.category'].search([('name','=',categ_str_list[-1].strip())],limit=1).id
                        else:
                            if categ_str_list[0].strip() not in set(category_list):
                                parent_object = self.env["product.category"].create({
                                                    'name':categ_str_list[0].strip(),
                                                    'parent_id':False,
                                                    'display_name':categ_str_list[0].strip()
                                                }).id
                                categ_id_val = self.env['product.category'].create({
                                                    'name':categ_str_list[-1].strip(),
                                                    'parent_id':parent_object,
                                                    'display_name':categ_id
                                                }).id
                            else:
                                id_obj = self.env['product.category'].search([('name','=',categ_str_list[0].strip())],limit=1)
                                categ_id_val = self.env['product.category'].create({
                                    'name':categ_str_list[-1].strip(),
                                    'parent_id':id_obj.id,
                                    'display_name':categ_id
                                }).id

                    elif len(categ_str_list) == 3:
                        if categ_str_list[-1].strip() in set(category_list):
                            if categ_str_list[1].strip() not in set(category_list):
                                parent_object = self.env["product.category"].create({
                                                    'name':categ_str_list[1].strip(),
                                                    'parent_id':1,
                                                    'display_name':categ_str_list[0].strip()
                                                }).id
                                categ_id_val = self.env['product.category'].create({
                                                    'name':categ_str_list[-1].strip(),
                                                    'parent_id':parent_object,
                                                    'display_name':categ_id
                                                }).id
                            else:
                                categ_id_val = self.env['product.category'].search([('name','=',categ_str_list[-1].strip())],limit=1).id
                        else:
                            if categ_str_list[1].strip() not in set(category_list):
                                parent_object = self.env["product.category"].create({
                                                    'name':categ_str_list[1].strip(),
                                                    'parent_id':1,
                                                    'display_name':categ_str_list[0].strip()
                                                }).id
                                categ_id_val = self.env['product.category'].create({
                                                    'name':categ_str_list[-1].strip(),
                                                    'parent_id':parent_object,
                                                    'display_name':categ_id
                                                }).id
                            else:
                                parent_object = self.env['product.category'].search([('name','=',categ_str_list[1].strip())],limit=1)                                
                                categ_id_val = self.env['product.category'].create({
                                                    'name':categ_str_list[-1].strip(),
                                                    'parent_id':parent_object.id,
                                                    'display_name':categ_id
                                                }).id

                taxes_id=sheet.cell(suits,7).value.split(",")
                tax_list=[]
                for name in taxes_id:
                    tax_obj=self.env["account.tax"].search([('name','=',name)])
                    if tax_obj:
                        for val in tax_obj:
                            tax_list.append(val.id)
            
                vendor_id=sheet.cell(suits,8).value.split(",")
                ven_tax_list=[]
                for name in vendor_id:
                    ven_obj=self.env["account.tax"].search([('name','=',name)])
                    if ven_obj:
                        for val in ven_obj:
                            ven_tax_list.append(val.id)

                uom_id=1
                uom_id_val=sheet.cell(suits,5).value
                uom_id_obj=self.env["uom.uom"].search([])
                for value in uom_id_obj:
                    if value.name == uom_id_val:
                        uom_id=value.id

                uom_po_id=1
                uom_po_id_val=sheet.cell(suits,6).value
                uom_po_id_obj=self.env["uom.uom"].search([])
                for value in uom_po_id_obj:
                    if value.name == uom_po_id_val:
                        uom_po_id=value.id

                invoice_policy=sheet.cell(suits, 10).value.lower().strip()
                if invoice_policy in "ordered quantities" or invoice_policy in "order":
                    invoice_policy_value="order"
                elif invoice_policy in "delivered quantities" or invoice_policy in "delivery":
                    invoice_policy_value="delivery"
                else:
                    raise UserError(_("Invoicing Policy must be in 'ordered quantities' and 'delivered quantities' "))


                product_type=str(sheet.cell(suits, 3).value).lower().strip()
                if product_type in "storable product" or product_type in "product":
                    product_type="product"
                elif product_type in "service":
                    product_type="service"
                else:
                    product_type="consu"

                attribute_ids = self.env["product.attribute"].search([])
                attrib_id_set = set(ids.name for ids in attribute_ids)
                product_attrib_ids = sheet.cell(suits, 13).value.split(",")

                attrib_id_list = []; exist_attribute_list = []
                for name in product_attrib_ids:
                    if len(name) != 0:
                        if name not in attrib_id_set:
                            attrib_id = self.env["product.attribute"].create({'name':name})
                            attrib_id_list.append(attrib_id)
                        else:
                            exist_attribute = self.env["product.attribute"].search([('name','=',name)])
                            exist_attribute_list.append(exist_attribute)

                union_list = list(set(attrib_id_list).union(exist_attribute_list))

                exist_attribute_values = self.env["product.attribute.value"].search([])
                exist_attrib_val_list = [attrib_name.name for attrib_name in exist_attribute_values]

                product_attrib_id_values = sheet.cell(suits, 14).value.split(",")
                values_lst = []
                for value in product_attrib_id_values:
                    if value not in exist_attrib_val_list:
                        for ids in union_list:
                            attrib_value_id = self.env["product.attribute.value"].create({
                                'attribute_id':ids.id,
                                'name':value
                            })
                            values_lst.append(attrib_value_id.id)
                    else:
                        for ids in exist_attribute_values:
                            if value == ids.name:
                                attrib_value_id = self.env["product.attribute.value"].browse(ids.id)
                                values_lst.append(attrib_value_id.id)


# ==============================xls with variant =================================================
                if self.method == 'with_var':

                    if uom_id_val != uom_po_id_val:
                        raise UserError(_("The default Unit of Measure and the purchase Unit of Measure must be in the same category. "))

                    temp_obj=self.env['product.template'].search([])

                    product_name=sheet.cell(suits, 0).value
                    if product_name not in product_dict.keys():

                        product_data={  'name':sheet.cell(suits, 0).value,
                                        
                                        'sale_ok':sheet.cell(suits, 1).value,
                                        'purchase_ok':sheet.cell(suits, 2).value,
                                        'type':product_type or "consu",
                                        'categ_id':categ_id_val or 1,
                                        'taxes_id':[(4,val,None) for val in tax_list] or False,
                                        'supplier_taxes_id':[(4,val,None) for val in ven_tax_list] or False,
                                        'description_sale':sheet.cell(suits, 9).value,
                                        'invoice_policy':invoice_policy_value,
                                        'list_price':sheet.cell(suits, 11).value,
                                        'standard_price':sheet.cell(suits, 12).value,
                                        'uom_id':uom_id or 1,
                                        'uom_po_id':uom_po_id or 1,
                                        'default_code':sheet.cell(suits, 15).value,
                                        }

                        main_product = self.env["product.template"].create(product_data)

                        many2many_field=sheet.cell(suits, 27).value.split(",")
                        custom_m2m_list=[]
                        for name in many2many_field:
                            m2m_obj=self.env["res.partner"].search([('name','=',name)], limit=1)
                            if m2m_obj:
                                custom_m2m_list.append(m2m_obj.id)


                        many2one_field=sheet.cell(suits, 26).value
                        res_partners=self.env["res.partner"].search([])
                        for partner in res_partners:
                            if partner.name == many2one_field:
                                main_product.write({'many2one_field':partner.id or False})

                        main_product.write({
                            'boolean_field':sheet.cell(suits, 21).value,
                            'many2many_field':[(4,val,None) for val in custom_m2m_list] or False,
                            'char_field':sheet.cell(suits, 22).value,
                            'integer_field':sheet.cell(suits, 23).value,
                            'float_field':sheet.cell(suits, 24).value,
                            'text_field':sheet.cell(suits, 25).value
                            })


                        for ids in union_list:
                            record = self.env['product.template.attribute.line'].create({
                                'attribute_id':ids.id,
                                'product_tmpl_id':main_product.id,
                                'value_ids':[(4, value) for value in values_lst]
                            })

                        count = 0
                        if main_product.attribute_line_ids:
                            main_product._create_variant_ids()
                            for value in main_product.attribute_line_ids.value_ids:
                                count+=1
                        
                        recent_product_product = self.env["product.product"].search([('name','=',product_name)])
                        for product in recent_product_product:
                            product.write({
                                            'sale_ok':sheet.cell(suits, 1).value,
                                            'purchase_ok':sheet.cell(suits, 2).value,
                                            'type':product_type or "consu",
                                            'categ_id':categ_id_val or 1,
                                            'taxes_id':[(4,val,None) for val in tax_list] or False,
                                            'supplier_taxes_id':[(4,val,None) for val in ven_tax_list] or False,
                                            'description_sale':sheet.cell(suits, 9).value,
                                            'invoice_policy':invoice_policy_value,
                                            'list_price':sheet.cell(suits, 11).value,
                                            'standard_price':sheet.cell(suits, 12).value,
                                            'default_code':sheet.cell(suits, 15).value,
                                            'weight':sheet.cell(suits, 17).value,
                                            'volume':sheet.cell(suits, 18).value
                                            })

                            new_quantity=sheet.cell(suits, 19).value

                            if product.type in 'product':
                                self.env['stock.change.product.qty'].create({
                                        'product_id': product.id,
                                        'product_tmpl_id':product.product_tmpl_id.id,
                                        'new_quantity': new_quantity
                                        }).change_product_qty()

                        product_dict[product_data['name']] = product_data['name']

                    else:
                        product=sheet.cell(suits, 0).value
                        product_template_object=self.env['product.template'].search([('name','=',product)],limit=1)
                        
                        many2many_field=sheet.cell(suits, 27).value.split(",")
                        custom_m2m_list=[]
                        for name in many2many_field:
                            m2m_obj=self.env["res.partner"].search([('name','=',name)],limit=1)
                            if m2m_obj:
                                custom_m2m_list.append(m2m_obj.id)
                                

                        many2one_field=sheet.cell(suits, 26).value
                        res_partners=self.env["res.partner"].search([])
                        for partner in res_partners:
                            if partner.name == many2one_field:
                                product_template_object.write({'many2one_field':partner.id or False})

                        product_template_object.write({
                            'boolean_field':sheet.cell(suits, 21).value,
                            'many2many_field':[(6,0,custom_m2m_list)] or False,
                            'char_field':sheet.cell(suits, 22).value,
                            'integer_field':sheet.cell(suits, 23).value,
                            'float_field':sheet.cell(suits, 24).value,
                            'text_field':sheet.cell(suits, 25).value
                            })

                        for ids in union_list:
                            record = self.env['product.template.attribute.line'].create({
                                'attribute_id':ids.id,
                                'product_tmpl_id':product_template_object.id,
                                'value_ids':[(4, value) for value in values_lst]
                            })

                        if product_template_object.attribute_line_ids:                            
                            product_template_object._create_variant_ids()
           
                        count = len(values_lst)
                        recent_product_product = self.env["product.product"].search([('name','=',product_name)])
                        for product in recent_product_product:
                            product.write({
                                            'sale_ok':sheet.cell(suits, 1).value,
                                            'purchase_ok':sheet.cell(suits, 2).value,
                                            'type':product_type or "consu",
                                            'categ_id':categ_id_val or 1,
                                            'taxes_id':[(4,val,None) for val in tax_list] or False,
                                            'supplier_taxes_id':[(4,val,None) for val in ven_tax_list] or False,
                                            'description_sale':sheet.cell(suits, 9).value,
                                            'invoice_policy':invoice_policy_value,
                                            'list_price':sheet.cell(suits, 11).value,
                                            'standard_price':sheet.cell(suits, 12).value,
                                            'default_code':sheet.cell(suits, 15).value,
                                            'weight':sheet.cell(suits, 17).value,
                                            'volume':sheet.cell(suits, 18).value
                                            })

                            new_quantity=sheet.cell(suits, 19).value
                            if product.type in 'product':
                                self.env['stock.change.product.qty'].create({
                                        'product_id': product.id,
                                        'product_tmpl_id':product.product_tmpl_id.id,
                                        'new_quantity': new_quantity
                                        }).change_product_qty()

# ===================================xls update var=====================================================
                elif self.method == 'update_var':

                    product_name=sheet.cell(suits, 0).value
                    if product_name not in product_dict.keys():

                        product_template=self.env['product.template'].search([('name','=',product)],limit=1)

                        if product_template:

                            for line in product_template.attribute_line_ids:
                                line.unlink()
                          

                            many2many_field=sheet.cell(suits, 27).value.split(",")
                            custom_m2m_list=[]
                            for name in many2many_field:
                                m2m_obj=self.env["res.partner"].search([('name','=',name)],limit=1)
                                if m2m_obj:
                                    custom_m2m_list.append(m2m_obj.id)

                            many2one_field=sheet.cell(suits, 26).value
                            res_partners=self.env["res.partner"].search([])
                            partner_id=False
                            for update_product in self.env['product.template'].search([('name','=',product)]):
                                for partner in res_partners:
                                    if partner.name == many2one_field:
                                        partner_id=partner.id

                                update_product.write({'many2many_field':[(6,0,custom_m2m_list)],
                                                      'many2one_field':partner_id or False})

                            product_template.write({
                                
                                'sale_ok':sheet.cell(suits, 1).value,
                                'purchase_ok':sheet.cell(suits, 2).value,
                                'type':product_type or "consu",
                                'categ_id':categ_id_val or 1,
                                'description_sale':sheet.cell(suits, 9).value,
                                'invoice_policy':invoice_policy_value,
                                'list_price':sheet.cell(suits, 11).value,
                                'standard_price':sheet.cell(suits, 12).value,
                                'default_code':sheet.cell(suits, 15).value,
                                'boolean_field':sheet.cell(suits, 21).value,
                                'char_field':sheet.cell(suits, 22).value,
                                'integer_field':sheet.cell(suits, 23).value,
                                'float_field':sheet.cell(suits, 24).value,
                                'text_field':sheet.cell(suits, 25).value,
                                
                                'many2many_field':[(6,0,custom_m2m_list)],
                                'taxes_id':[(6,0,tax_list)],
                                'supplier_taxes_id':[(6,0,ven_tax_list)]
                                })

                            for ids in union_list:
                                record = self.env['product.template.attribute.line'].create({
                                'attribute_id':ids.id,
                                'product_tmpl_id':product_template.id,
                                'value_ids':[(4, value) for value in values_lst]
                                })

                            if product_template.attribute_line_ids:                            
                                product_template._create_variant_ids()
               
                            count = len(values_lst)
                            recent_product_product = self.env["product.product"].search([('name','=',product_name)])[:-count-1:-1]
                            for product in recent_product_product:
                                product.write({
                                                'sale_ok':sheet.cell(suits, 1).value,
                                                'purchase_ok':sheet.cell(suits, 2).value,
                                                'type':product_type or "consu",
                                                'categ_id':categ_id_val or 1,
                                                'taxes_id':[(4,val,None) for val in tax_list] or False,
                                                'supplier_taxes_id':[(4,val,None) for val in ven_tax_list] or False,
                                                'description_sale':sheet.cell(suits, 9).value,
                                                'invoice_policy':invoice_policy_value,
                                                'list_price':sheet.cell(suits, 11).value,
                                                'standard_price':sheet.cell(suits, 12).value,
                                                'default_code':sheet.cell(suits, 15).value,
                                                'weight':sheet.cell(suits, 17).value,
                                                'volume':sheet.cell(suits, 18).value
                                                })

                   
                                new_quantity=sheet.cell(suits, 19).value

                                if product.type in 'product':
                                    self.env['stock.change.product.qty'].create({
                                                'product_id': product.id,
                                                'product_tmpl_id':product.product_tmpl_id.id,
                                                'new_quantity': new_quantity
                                                }).change_product_qty()

                            product_dict[product_name] =product_name

                        else:
                            temp_obj=self.env['product.template'].search([])
                            product_name=sheet.cell(suits, 0).value
                            
                            product_data={  'name':sheet.cell(suits, 0).value,
                                            
                                            'sale_ok':sheet.cell(suits, 1).value,
                                            'purchase_ok':sheet.cell(suits, 2).value,
                                            'type':product_type or "consu",
                                            'categ_id':categ_id_val or 1,
                                            'taxes_id':[(4,val,None) for val in tax_list] or False,
                                            'supplier_taxes_id':[(4,val,None) for val in ven_tax_list] or False,
                                            'description_sale':sheet.cell(suits, 9).value,
                                            'invoice_policy':invoice_policy_value,
                                            'list_price':sheet.cell(suits, 11).value,
                                            'standard_price':sheet.cell(suits, 12).value,
                                            'uom_id':uom_id or 1,
                                            'uom_po_id':uom_po_id or 1,
                                            'default_code':sheet.cell(suits, 15).value,
                                            }

                            main_product = self.env["product.template"].create(product_data)

                            many2many_field=sheet.cell(suits, 27).value.split(",")
                            custom_m2m_list=[]
                            for name in many2many_field:
                                m2m_obj=self.env["res.partner"].search([('name','=',name)],limit=1)
                                if m2m_obj:
                                    custom_m2m_list.append(m2m_obj.id)


                            many2one_field=sheet.cell(suits, 26).value
                            res_partners=self.env["res.partner"].search([])
                            for partner in res_partners:
                                if partner.name == many2one_field:
                                    main_product.write({'many2one_field':partner.id or False})

                            main_product.write({
                                'boolean_field':sheet.cell(suits, 21).value,
                                'many2many_field':[(4,val,None) for val in custom_m2m_list] or False,
                                'char_field':sheet.cell(suits, 22).value,
                                'integer_field':sheet.cell(suits, 23).value,
                                'float_field':sheet.cell(suits, 24).value,
                                'text_field':sheet.cell(suits, 25).value
                                })


                            for ids in union_list:
                                record = self.env['product.template.attribute.line'].create({
                                    'attribute_id':ids.id,
                                    'product_tmpl_id':main_product.id,
                                    'value_ids':[(4, value) for value in values_lst]
                                })

                            count = 0
                            if main_product.attribute_line_ids:
                                main_product._create_variant_ids()
                                for value in main_product.attribute_line_ids.value_ids:
                                    count+=1
                            
                            recent_product_product = self.env["product.product"].search([('name','=',product_name)])[:-count-1:-1]
                            for product in recent_product_product:
                                product.write({
                                                'sale_ok':sheet.cell(suits, 1).value,
                                                'purchase_ok':sheet.cell(suits, 2).value,
                                                'type':product_type or "consu",
                                                'categ_id':categ_id_val or 1,
                                                'taxes_id':[(4,val,None) for val in tax_list] or False,
                                                'supplier_taxes_id':[(4,val,None) for val in ven_tax_list] or False,
                                                'description_sale':sheet.cell(suits, 9).value,
                                                'invoice_policy':invoice_policy_value,
                                                'list_price':sheet.cell(suits, 11).value,
                                                'standard_price':sheet.cell(suits, 12).value,
                                                'default_code':sheet.cell(suits, 15).value,
                                                'weight':sheet.cell(suits, 17).value,
                                                'volume':sheet.cell(suits, 18).value
                                                })

                                new_quantity=sheet.cell(suits, 19).value

                                if product.type in 'product':
                                    self.env['stock.change.product.qty'].create({
                                            'product_id': product.id,
                                            'product_tmpl_id':product.product_tmpl_id.id,
                                            'new_quantity': new_quantity
                                            }).change_product_qty()

                            product_dict[product_name] =product_name

                    else:
                        product=sheet.cell(suits, 0).value
                        product_template_object=self.env['product.template'].search([('name','=',product)],limit=1)
                        
                        many2many_field=sheet.cell(suits, 27).value.split(",")
                        custom_m2m_list=[]
                        for name in many2many_field:
                            m2m_obj=self.env["res.partner"].search([('name','=',name)],limit=1)
                            if m2m_obj:
                                custom_m2m_list.append(m2m_obj.id)
                                

                        many2one_field=sheet.cell(suits, 26).value
                        res_partners=self.env["res.partner"].search([])
                        for partner in res_partners:
                            if partner.name == many2one_field:
                                product_template_object.write({'many2one_field':partner.id or False})

                        product_template_object.write({
                            'boolean_field':sheet.cell(suits, 21).value,
                            'many2many_field':[(6,0,custom_m2m_list)] or False,
                            'char_field':sheet.cell(suits, 22).value,
                            'integer_field':sheet.cell(suits, 23).value,
                            'float_field':sheet.cell(suits, 24).value,
                            'text_field':sheet.cell(suits, 25).value
                            })

                        for ids in union_list:
                            record = self.env['product.template.attribute.line'].create({
                                'attribute_id':ids.id,
                                'product_tmpl_id':product_template_object.id,
                                'value_ids':[(4, value) for value in values_lst]
                            })

                        if product_template_object.attribute_line_ids:                            
                            product_template_object._create_variant_ids()
           
                        count = len(values_lst)
                        recent_product_product = self.env["product.product"].search([('name','=',product_name)])[:-count-1:-1]
                        for product in recent_product_product:
                            product.write({
                                            'sale_ok':sheet.cell(suits, 1).value,
                                            'purchase_ok':sheet.cell(suits, 2).value,
                                            'type':product_type or "consu",
                                            'categ_id':categ_id_val or 1,
                                            'taxes_id':[(4,val,None) for val in tax_list] or False,
                                            'supplier_taxes_id':[(4,val,None) for val in ven_tax_list] or False,
                                            'description_sale':sheet.cell(suits, 9).value,
                                            'invoice_policy':invoice_policy_value,
                                            'list_price':sheet.cell(suits, 11).value,
                                            'standard_price':sheet.cell(suits, 12).value,
                                            'default_code':sheet.cell(suits, 15).value,
                                            'weight':sheet.cell(suits, 17).value,
                                            'volume':sheet.cell(suits, 18).value
                                            })

                            new_quantity=sheet.cell(suits, 19).value
                            if product.type in 'product':
                                self.env['stock.change.product.qty'].create({
                                        'product_id': product.id,
                                        'product_tmpl_id':product.product_tmpl_id.id,
                                        'new_quantity': new_quantity
                                        }).change_product_qty()


# ===================CSV==============================
        
        elif self.file_type  == 'csv':
            file_name = str(self.file_name)
            if self.importing_file:
                if '.' not in file_name:
                    raise UserError(_('Please upload valid CSV file...!'))
                extension = file_name.split('.')[1]
                if extension not in ['csv','CSV']:
                    raise UserError(_('Please upload only csv file.!'))

            product_dict={};categ_id_val=1;
            with io.BytesIO(base64.b64decode(self.importing_file)) as f:
                readers = csv.DictReader(codecs.iterdecode(f,'utf-8'))
                for row in readers:

                    product=row['Name']
                    if not product:
                        raise UserError(_("Product Name is missing !!"))

                    category_list=[]
                    for ids in self.env["product.category"].search([]):
                        category_list.append(ids.name)                

                    categ_id=(row['Category']).strip()
                    if categ_id:
                        categ_str_list=categ_id.split('/')
                        if len(categ_str_list) == 1:
                            if categ_str_list[0].strip() in set(category_list):
                                categ_id_val = self.env['product.category'].search([('name','=',categ_str_list[0].strip())],limit=1).id
                            else:
                                categ_id_val = self.env['product.category'].create({
                                    'name':categ_str_list[0].strip(),
                                    'parent_id':False,
                                    'display_name':categ_id
                                }).id

                        elif len(categ_str_list) == 2:
                            if categ_str_list[-1].strip() in set(category_list):
                                if categ_str_list[0].strip() not in set(category_list):
                                    
                                    parent_object = self.env["product.category"].create({
                                                        'name':categ_str_list[0].strip(),
                                                        'parent_id':False,
                                                        'display_name':categ_str_list[0].strip()
                                                    }).id
                                    categ_id_val = self.env['product.category'].create({
                                                        'name':categ_str_list[-1].strip(),
                                                        'parent_id':parent_object,
                                                        'display_name':categ_id
                                                    }).id
                                else:
                                    categ_id_val = self.env['product.category'].search([('name','=',categ_str_list[-1].strip())],limit=1).id
                            else:
                                if categ_str_list[0].strip() not in set(category_list):
                                    parent_object = self.env["product.category"].create({
                                                        'name':categ_str_list[0].strip(),
                                                        'parent_id':False,
                                                        'display_name':categ_str_list[0].strip()
                                                    }).id
                                    categ_id_val = self.env['product.category'].create({
                                                        'name':categ_str_list[-1].strip(),
                                                        'parent_id':parent_object,
                                                        'display_name':categ_id
                                                    }).id
                                else:
                                    id_obj = self.env['product.category'].search([('name','=',categ_str_list[0].strip())],limit=1)
                                    categ_id_val = self.env['product.category'].create({
                                        'name':categ_str_list[-1].strip(),
                                        'parent_id':id_obj.id,
                                        'display_name':categ_id
                                    }).id

                        elif len(categ_str_list) == 3:
                            if categ_str_list[-1].strip() in set(category_list):
                                if categ_str_list[1].strip() not in set(category_list):
                                    parent_object = self.env["product.category"].create({
                                                        'name':categ_str_list[1].strip(),
                                                        'parent_id':1,
                                                        'display_name':categ_str_list[0].strip()
                                                    }).id
                                    categ_id_val = self.env['product.category'].create({
                                                        'name':categ_str_list[-1].strip(),
                                                        'parent_id':parent_object,
                                                        'display_name':categ_id
                                                    }).id
                                else:
                                    categ_id_val = self.env['product.category'].search([('name','=',categ_str_list[-1].strip())],limit=1).id
                            else:
                                if categ_str_list[1].strip() not in set(category_list):
                                    parent_object = self.env["product.category"].create({
                                                        'name':categ_str_list[1].strip(),
                                                        'parent_id':1,
                                                        'display_name':categ_str_list[0].strip()
                                                    }).id
                                    categ_id_val = self.env['product.category'].create({
                                                        'name':categ_str_list[-1].strip(),
                                                        'parent_id':parent_object,
                                                        'display_name':categ_id
                                                    }).id
                                else:
                                    parent_object = self.env['product.category'].search([('name','=',categ_str_list[1].strip())],limit=1)                                
                                    categ_id_val = self.env['product.category'].create({
                                                        'name':categ_str_list[-1].strip(),
                                                        'parent_id':parent_object.id,
                                                        'display_name':categ_id
                                                    }).id

                    taxes_id=(row['Customer Taxes']).split(",")
                    tax_list=[]
                    for name in taxes_id:
                        tax_obj=self.env["account.tax"].search([('name','=',name)])
                        if tax_obj:
                            for val in tax_obj:
                                tax_list.append(val.id)

                    vendor_id=(row['Vendor Taxes']).split(",")
                    ven_tax_list=[]
                    for name in vendor_id:
                        ven_obj=self.env["account.tax"].search([('name','=',name)])
                        if ven_obj:
                            for val in ven_obj:
                                ven_tax_list.append(val.id)

                    uom_id=1
                    uom_id_val=(row['Unit of measurment'])
                    uom_id_obj=self.env["uom.uom"].search([])
                    for value in uom_id_obj:
                        if value.name == uom_id_val:
                            uom_id=value.id

                    uom_po_id=1
                    uom_po_id_val=(row['Purchase unit of Measure'])
                    uom_po_id_obj=self.env["uom.uom"].search([])
                    for value in uom_po_id_obj:
                        if value.name == uom_po_id_val:
                            uom_po_id=value.id


                    invoice_policy=(row['Invoicing Policy']).lower().strip()
                    if invoice_policy in "ordered quantities" or invoice_policy in "order":
                        invoice_policy_value="order"
                    elif invoice_policy in "delivered quantities" or invoice_policy in "delivery":
                        invoice_policy_value="delivery"
                    else:
                        raise UserError(_("Invoicing Policy must be in 'ordered quantities' and 'delivered quantities' "))


                    product_type=str(row['Product Type']).lower().strip()
                    if product_type in "storable product" or product_type in "product":
                        product_type="product"
                    elif product_type in "service":
                        product_type="service"
                    else:
                        product_type="consu"
# ==================================================================================================
                    
                    attribute_ids = self.env["product.attribute"].search([])
                    attrib_id_set = set(ids.name for ids in attribute_ids)
                    product_attrib_ids = row['Variant Attributes'].split(",")

                    attrib_id_list = []; exist_attribute_list = []
                    for name in product_attrib_ids:
                        if len(name) != 0:
                            if name not in attrib_id_set:
                                attrib_id = self.env["product.attribute"].create({'name':name})
                                attrib_id_list.append(attrib_id)
                            else:
                                exist_attribute = self.env["product.attribute"].search([('name','=',name)])
                                exist_attribute_list.append(exist_attribute)

                    union_list = list(set(attrib_id_list).union(exist_attribute_list))

                    exist_attribute_values = self.env["product.attribute.value"].search([])
                    exist_attrib_val_list = [attrib_name.name for attrib_name in exist_attribute_values]

                    product_attrib_id_values = row['Attribute Values'].split(",")
                    values_lst = []
                    for value in product_attrib_id_values:
                        if value not in exist_attrib_val_list:
                            for ids in union_list:
                                attrib_value_id = self.env["product.attribute.value"].create({
                                    'attribute_id':ids.id,
                                    'name':value
                                })
                                values_lst.append(attrib_value_id.id)
                        else:
                            for ids in exist_attribute_values:
                                if value == ids.name:
                                    attrib_value_id = self.env["product.attribute.value"].browse(ids.id)
                                    values_lst.append(attrib_value_id.id)



# =============================CSV create variant===================================================
                    if self.method == 'with_var':

                        temp_obj=self.env['product.template'].search([])
                        product_name=row['Name']
                        if product_name not in product_dict.keys():
                            product_data={
                                'name':(row['Name']),
                                # 'image_1920':new_image,
                                'sale_ok':(row['Can be Sold']),
                                'purchase_ok':(row['Can be Purchased']),
                                'type':product_type or "consu",
                                'categ_id':categ_id_val or 1,
                                'taxes_id':[(4,val,None) for val in tax_list],
                                'supplier_taxes_id':[(4,val,None) for val in ven_tax_list],
                                'description_sale':(row['Description for customer']),
                                'invoice_policy':invoice_policy_value,
                                'list_price':(row['Sales Price']),
                                'standard_price':(row['Cost']),
                                'uom_id':uom_id or 1,
                                'uom_po_id':uom_po_id or 1,
                                'default_code':(row['Internal reference']),
                                }

                            main_product = self.env["product.template"].create(product_data)

                            many2many_field=(row['many2many_field']).split(",")
                            custom_m2m_list=[]
                            for name in many2many_field:
                                m2m_obj=self.env["res.partner"].search([('name','=',name)],limit=1)
                                if m2m_obj:
                                    custom_m2m_list.append(m2m_obj.id)

                            many2one_field=(row['many2one_field'])
                            res_partners=self.env["res.partner"].search([])
                            for partner in res_partners:
                                if partner.name == many2one_field:
                                    main_product.write({'many2one_field':partner.id or False})


                            main_product.write({
                                'boolean_field':(row['boolean_field']),
                                'many2many_field':[(4,val,None) for val in custom_m2m_list] or False,
                                'char_field':(row['char_field']),
                                'integer_field':(row['integer_field']),
                                'float_field':(row['float_field']),
                                'text_field':(row['text_field'])
                                })

                            for ids in union_list:
                                record = self.env['product.template.attribute.line'].create({
                                    'attribute_id':ids.id,
                                    'product_tmpl_id':main_product.id,
                                    'value_ids':[(4, value) for value in values_lst]
                                })

                            count = 0
                            if main_product.attribute_line_ids:
                                main_product._create_variant_ids()
                                for value in main_product.attribute_line_ids.value_ids:
                                    count+=1
                            
                            recent_product_product = self.env["product.product"].search([('name','=',product_name)])[:-count-1:-1]
                            for product in recent_product_product:
                                product.write({
                                                'sale_ok':(row['Can be Sold']),
                                                'purchase_ok':(row['Can be Purchased']),
                                                'type':product_type or "consu",
                                                'categ_id':categ_id_val or 1,
                                                'taxes_id':[(4,val,None) for val in tax_list] or False,
                                                'supplier_taxes_id':[(4,val,None) for val in ven_tax_list],
                                                'description_sale':(row['Description for customer']),
                                                'invoice_policy':invoice_policy_value,
                                                'list_price':(row['Sales Price']),
                                                'standard_price':(row['Cost']),
                                                'default_code':(row['Internal reference']),
                                                'weight':(row['Weight']),
                                                'volume':(row['Volume'])
                                                })

                                new_quantity=(row['Qty On Hand'])
                                if product.type in 'product':
                                    self.env['stock.change.product.qty'].create({
                                            'product_id': product.id,
                                            'product_tmpl_id':product.product_tmpl_id.id,
                                            'new_quantity': new_quantity
                                            }).change_product_qty()

                            product_dict[product_data['name']] = product_data['name']

                        else:
                            product=row['Name']
                            product_template_object=self.env['product.template'].search([('name','=',product)],limit=1)

                            many2many_field=(row['many2many_field']).split(",")
                            custom_m2m_list=[]
                            for name in many2many_field:
                                m2m_obj=self.env["res.partner"].search([('name','=',name)],limit=1)
                                if m2m_obj:
                                    custom_m2m_list.append(m2m_obj.id)

                            many2one_field=(row['many2one_field'])
                            res_partners=self.env["res.partner"].search([])
                            for partner in res_partners:
                                if partner.name == many2one_field:
                                    product_template_object.write({'many2one_field':partner.id or False})

                            product_template_object.write({
                                'boolean_field':(row['boolean_field']),
                                'many2many_field':[(6,0,custom_m2m_list)] or False,
                                'char_field':(row['char_field']),
                                'integer_field':(row['integer_field']),
                                'float_field':(row['float_field']),
                                'text_field':(row['text_field'])
                                })

                            for ids in union_list:
                                record = self.env['product.template.attribute.line'].create({
                                    'attribute_id':ids.id,
                                    'product_tmpl_id':product_template_object.id,
                                    'value_ids':[(4, value) for value in values_lst]
                                })

                            if product_template_object.attribute_line_ids:                            
                                product_template_object._create_variant_ids()
               
                            count = len(values_lst)
                            recent_product_product = self.env["product.product"].search([('name','=',product_name)])
                            for product in recent_product_product:
                                product.write({
                                                'sale_ok':(row['Can be Sold']),
                                                'purchase_ok':(row['Can be Purchased']),
                                                'type':product_type or "consu",
                                                'categ_id':categ_id_val or 1,
                                                'taxes_id':[(4,val,None) for val in tax_list] or False,
                                                'supplier_taxes_id':[(4,val,None) for val in ven_tax_list],
                                                'description_sale':(row['Description for customer']),
                                                'invoice_policy':invoice_policy_value,
                                                'list_price':(row['Sales Price']),
                                                'standard_price':(row['Cost']),
                                                'default_code':(row['Internal reference']),
                                                'weight':(row['Weight']),
                                                'volume':(row['Volume'])
                                                })

                                new_quantity=(row['Qty On Hand'])
                                if product.type in 'product':
                                    self.env['stock.change.product.qty'].create({
                                            'product_id': product.id,
                                            'product_tmpl_id':product.product_tmpl_id.id,
                                            'new_quantity': new_quantity
                                            }).change_product_qty()

# =================================CSV update variant====================================================

                    elif self.method == 'update_var':

                        product_name=row['Name']
                        if product_name not in product_dict.keys():
                            product_template=self.env['product.template'].search([('name','=',product)],limit=1)
                            
                            if product_template:
                                for line in product_template.attribute_line_ids:
                                    line.unlink()

                                many2many_field=(row['many2many_field']).split(",")
                                custom_m2m_list=[]
                                for name in many2many_field:
                                    m2m_obj=self.env["res.partner"].search([('name','=',name)],limit=1)
                                    if m2m_obj:
                                        custom_m2m_list.append(m2m_obj.id)

                                many2one_field=(row['many2one_field'])
                                res_partners=self.env["res.partner"].search([])

                                partner_id=False
                                for update_product in self.env['product.template'].search([('name','=',product)]):
                                    for partner in res_partners:
                                        if partner.name == many2one_field:
                                            partner_id=partner.id
                                            
                                    update_product.write({'many2many_field':[(6,0,custom_m2m_list)],
                                                            'many2one_field':partner_id or False})

                                product_template.write({
                                    
                                    'sale_ok':(row['Can be Sold']),
                                    'purchase_ok':(row['Can be Purchased']),
                                    'type':product_type or "consu",
                                    'categ_id':categ_id_val or 1,
                                    'description_sale':(row['Description for customer']),
                                    'invoice_policy':invoice_policy_value,
                                    'list_price':(row['Sales Price']),
                                    'standard_price':(row['Cost']),
                                    'default_code':(row['Internal reference']),
                                    
                                    'boolean_field':(row['boolean_field']),
                                    'many2many_field':[(6,0,custom_m2m_list)] or False,
                                    'char_field':(row['char_field']),
                                    'integer_field':(row['integer_field']),
                                    'float_field':(row['float_field']),
                                    'text_field':(row['text_field']),

                                    'taxes_id':[(6,0,tax_list)] or False,
                                    'supplier_taxes_id':[(6,0,ven_tax_list)] or False
                                    })

                                for ids in union_list:
                                    record = self.env['product.template.attribute.line'].create({
                                    'attribute_id':ids.id,
                                    'product_tmpl_id':product_template.id,
                                    'value_ids':[(4, value) for value in values_lst]
                                    })

                                if product_template.attribute_line_ids:                            
                                    product_template._create_variant_ids()

                                count = len(values_lst)
                                recent_product_product = self.env["product.product"].search([('name','=',product_name)])[:-count-1:-1]
                                for product in recent_product_product:

                                    product.update({
                                        
                                        'sale_ok':(row['Can be Sold']),
                                        'purchase_ok':(row['Can be Purchased']),
                                        'type':product_type,
                                        'categ_id':categ_id_val,
                                        'taxes_id':[(6,0,tax_list)] or False,
                                        'supplier_taxes_id':[(6,0,ven_tax_list)] or False,
                                        'description_sale':(row['Description for customer']),
                                        'invoice_policy':invoice_policy_value,
                                        'list_price':(row['Sales Price']),
                                        'standard_price':(row['Cost']),
                                        'default_code':(row['Internal reference']),
                                        'weight':(row['Weight']),
                                        'volume':(row['Volume'])
                                        })

                                    new_quantity=(row['Qty On Hand'])
                                    if product.type in 'product':
                                        self.env['stock.change.product.qty'].create({
                                                'product_id': product.id,
                                                'product_tmpl_id':product.product_tmpl_id.id,
                                                'new_quantity': new_quantity,
                                                }).change_product_qty()

                                product_dict[product_name] =product_name
 
                            else:

                                temp_obj=self.env['product.template'].search([])
                                
                                product_name=row['Name']

                                product_data={
                                'name':(row['Name']),
                                
                                'sale_ok':(row['Can be Sold']),
                                'purchase_ok':(row['Can be Purchased']),
                                'type':product_type or "consu",
                                'categ_id':categ_id_val or 1,
                                'taxes_id':[(4,val,None) for val in tax_list] or False,
                                'supplier_taxes_id':[(4,val,None) for val in ven_tax_list] or False,
                                'description_sale':(row['Description for customer']),
                                'invoice_policy':invoice_policy_value,
                                'list_price':(row['Sales Price']),
                                'standard_price':(row['Cost']),
                                'uom_id':uom_id or 1,
                                'uom_po_id':uom_po_id or 1,
                                'default_code':(row['Internal reference']),
                                }

                                main_product = self.env["product.template"].create(product_data)

                                many2many_field=(row['many2many_field']).split(",")
                                custom_m2m_list=[]
                                for name in many2many_field:
                                    m2m_obj=self.env["res.partner"].search([('name','=',name)],limit=1)
                                    if m2m_obj:
                                        custom_m2m_list.append(m2m_obj.id)

                                many2one_field=(row['many2one_field'])
                                res_partners=self.env["res.partner"].search([])
                                for partner in res_partners:
                                    if partner.name == many2one_field:
                                        main_product.write({'many2one_field':partner.id or False})

                                main_product.write({
                                    'boolean_field':(row['boolean_field']),
                                    'many2many_field':[(4,val,None) for val in custom_m2m_list] or False,
                                    'char_field':(row['char_field']),
                                    'integer_field':(row['integer_field']),
                                    'float_field':(row['float_field']),
                                    'text_field':(row['text_field'])
                                    })

                                for ids in union_list:
                                    record = self.env['product.template.attribute.line'].create({
                                        'attribute_id':ids.id,
                                        'product_tmpl_id':main_product.id,
                                        'value_ids':[(4, value) for value in values_lst]
                                    })

                                count = 0
                                if main_product.attribute_line_ids:
                                    main_product._create_variant_ids()
                                    for value in main_product.attribute_line_ids.value_ids:
                                        count+=1
                                
                                recent_product_product = self.env["product.product"].search([('name','=',product_name)])[:-count-1:-1]
                                for product in recent_product_product:
                                    product.write({
                                                    'sale_ok':(row['Can be Sold']),
                                                    'purchase_ok':(row['Can be Purchased']),
                                                    'type':product_type or "consu",
                                                    'categ_id':categ_id_val or 1,
                                                    'taxes_id':[(4,val,None) for val in tax_list] or False,
                                                    'supplier_taxes_id':[(4,val,None) for val in ven_tax_list] or False,
                                                    'description_sale':(row['Description for customer']),
                                                    'invoice_policy':invoice_policy_value,
                                                    'list_price':(row['Sales Price']),
                                                    'standard_price':(row['Cost']),
                                                    'default_code':(row['Internal reference']),
                                                    'weight':(row['Weight']),
                                                    'volume':(row['Volume'])
                                                    })

                                    new_quantity=(row['Qty On Hand'])
                                    if product.type in 'product':
                                        self.env['stock.change.product.qty'].create({
                                                'product_id': product.id,
                                                'product_tmpl_id':product.product_tmpl_id.id,
                                                'new_quantity': new_quantity
                                                }).change_product_qty()

                                product_dict[product_name] =product_name

                        else:
                            
                            product=row['Name']
                            product_template_object=self.env['product.template'].search([('name','=',product)],limit=1)

                            many2many_field=(row['many2many_field']).split(",")
                            custom_m2m_list=[]
                            for name in many2many_field:
                                m2m_obj=self.env["res.partner"].search([('name','=',name)],limit=1)
                                if m2m_obj:
                                    custom_m2m_list.append(m2m_obj.id)

                            many2one_field=(row['many2one_field'])
                            res_partners=self.env["res.partner"].search([])
                            for partner in res_partners:
                                if partner.name == many2one_field:
                                    product_template_object.write({'many2one_field':partner.id or False})

                            product_template_object.write({
                                'boolean_field':(row['boolean_field']),
                                'many2many_field':[(6,0,custom_m2m_list)] or False,
                                'char_field':(row['char_field']),
                                'integer_field':(row['integer_field']),
                                'float_field':(row['float_field']),
                                'text_field':(row['text_field'])
                                })

                            for ids in union_list:
                                record = self.env['product.template.attribute.line'].create({
                                    'attribute_id':ids.id,
                                    'product_tmpl_id':product_template_object.id,
                                    'value_ids':[(4, value) for value in values_lst]
                                })

                            if product_template_object.attribute_line_ids:                            
                                product_template_object._create_variant_ids()
               
                            count = len(values_lst)
                            recent_product_product = self.env["product.product"].search([('name','=',product_name)])
                            for product in recent_product_product:
                                product.write({
                                                'sale_ok':(row['Can be Sold']),
                                                'purchase_ok':(row['Can be Purchased']),
                                                'type':product_type or "consu",
                                                'categ_id':categ_id_val or 1,
                                                'taxes_id':[(4,val,None) for val in tax_list] or False,
                                                'supplier_taxes_id':[(4,val,None) for val in ven_tax_list],
                                                'description_sale':(row['Description for customer']),
                                                'invoice_policy':invoice_policy_value,
                                                'list_price':(row['Sales Price']),
                                                'standard_price':(row['Cost']),
                                                'default_code':(row['Internal reference']),
                                                'weight':(row['Weight']),
                                                'volume':float(row['Volume'])
                                                })

                                new_quantity=(row['Qty On Hand'])
                                if product.type in 'product':
                                    self.env['stock.change.product.qty'].create({
                                            'product_id': product.id,
                                            'product_tmpl_id':product.product_tmpl_id.id,
                                            'new_quantity': new_quantity
                                            }).change_product_qty()



        return {
                'name': 'Success',
                'view_mode': 'form',
                'res_model': 'success',
                'view_type': 'form',
                'type': 'ir.actions.act_window',
                'target': 'new',
            }

    def sample_csv(self):
        name_of_file = 'sample_with_variant.csv'
        file_path = 'export' + '.csv'
        value_list=[]
        with open('export.csv', mode='w') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(['PRODUCT NAME', 'CAN BE SOLD', 'CAN BE PURCHASED', 'PRODUCT TYPE','ALL / SALEABLE','UNITS','UNITS','CUSTOMER TAXES','VENDOR TAXES','DESCRIPTION FOR CUSTOMER','INVOICING POLICY','SALES PRICE','COST','VARIANT ATTRIBUTES','ATTRIBUTE VALUES','INTERNAL REFERENCE','WEIGHT','VOLUME','QTY ON HAND','IMAGE PATH/URL','boolean_field','char_field','integer_field','float_field','text_field','many2one_field','many2many_field'])
            writer.writerow(['Storage Box', 'True', 'True', 'product','All / Saleable','Units','Units','GST 1%','5%','Standard Product A','Ordered quantities',500,400,'colour','red','E-COM08',99,100,100,'/home/user_system_name/Pictures/ball_b.jpeg','True','Char A',1,2.5,'Text A','Administrator','Administrator,My Company'])
            csv_file.close()
        
        export_id = base64.b64encode(open(file_path, 'rb+').read())
        result_id = self.env['sample.download'].create({'file': export_id ,'file_name': name_of_file})

        return {
                'name': 'Download Sample Excel/CSV',
                'view_mode': 'form',
                'res_id': result_id.id,
                'res_model': 'sample.download',
                'view_type': 'form',
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
 
    def sample_xls(self):
        file_name = str(self.file_name)
        if self.importing_file:
            if '.' not in file_name:
                raise UserError(_('Please upload valid CSV file...!'))
            extension = file_name.split('.')[1]
            if extension not in ['csv','CSV']:
                raise UserError(_('Please upload only csv file.!'))
            
        name_of_file = 'sample_with_variant.xls'
        file_path = 'sample_with_variant' + '.xls'
        workbook = xlsxwriter.Workbook('/tmp/'+file_path)
        worksheet = workbook.add_worksheet()

        worksheet.write(0,0,"Product Name")
        worksheet.write(0,1,"Can be Sold")
        worksheet.write(0,2,"Can be Purchased")
        worksheet.write(0,3,"Product Type")
        worksheet.write(0,4,"Category")
        worksheet.write(0,5,"Unit of measurment")
        worksheet.write(0,6,"Purchase unit of Measure")
        worksheet.write(0,7,"Customer Taxes")
        worksheet.write(0,8,"Vendor Taxes")
        worksheet.write(0,9,"Description for customer")
        worksheet.write(0,10,"Invoicing Policy")
        worksheet.write(0,11,"Sales Price")
        worksheet.write(0,12,"Cost")
        worksheet.write(0,13,"Variant Attributes")
        worksheet.write(0,14,"Attribute Values")
        worksheet.write(0,15,"Internal reference")
        worksheet.write(0,16,"Weight")
        worksheet.write(0,17,"Volume")
        worksheet.write(0,18,"Qty On Hand")
        worksheet.write(0,19,"Image path/url")
        worksheet.write(0,20,"boolean_field")
        worksheet.write(0,21,"char_field")
        worksheet.write(0,22,"integer_field")
        worksheet.write(0,23,"float_field")
        worksheet.write(0,24,"text_field")
        worksheet.write(0,25,"many2one_field")
        worksheet.write(0,26,"many2many_field")

        worksheet.write(1,0,'Storage Box')
        worksheet.write(1,1,'True')
        worksheet.write(1,2,'True')
        worksheet.write(1,3,'product')
        worksheet.write(1,4,'All / Saleable')
        worksheet.write(1,5,'Units')
        worksheet.write(1,6,'Units')
        worksheet.write(1,7,'GST 1%')
        worksheet.write(1,8,'5%')
        worksheet.write(1,9,'Standard Product')
        worksheet.write(1,10,'Ordered quantities')
        worksheet.write(1,11,500)
        worksheet.write(1,12,400)
        worksheet.write(1,13,'colour')
        worksheet.write(1,14,'red')
        worksheet.write(1,15,'E-COM08')
        worksheet.write(1,16,99)
        worksheet.write(1,17,100)
        worksheet.write(1,18,100)
        worksheet.write(1,19,'/home/user_system_name/Pictures/ball_b.jpeg')
        worksheet.write(1,20,'Char A')
        worksheet.write(1,21,1)
        worksheet.write(1,22,2.1)
        worksheet.write(1,23,'Text A')
        worksheet.write(1,24,'Administrator')
        worksheet.write(1,25,'Administrator,My Company')        
        workbook.close()


        export_id = base64.b64encode(open('/tmp/' + file_path, 'rb+').read())
        result_id = self.env['sample.download'].create({'file': export_id ,'file_name': name_of_file})
        return {
                'name': 'Download Sample Excel/CSV',
                'view_mode': 'form',
                'res_id': result_id.id,
                'res_model': 'sample.download',
                'view_type': 'form',
                'type': 'ir.actions.act_window',
                'target': 'new',
            }


class sample_download(models.Model):
    _name="sample.download"
    _description="sample_download"

    file=fields.Binary("Download File")
    file_name = fields.Char(string="File Name")

                            
class ImportSales(models.Model):
    _inherit="sale.order"

class productcategory(models.Model):
    _inherit="product.category"    

class Success(models.Model):
    _name="success"

class ProductProduct(models.Model):
    _inherit = 'product.template'

    boolean_field=fields.Boolean("Boolean Field")
    many2many_field=fields.Many2many("res.partner",string="Customers")
    char_field=fields.Char("Characters")
    integer_field=fields.Integer("Integer")
    float_field=fields.Float("Float")
    text_field=fields.Text("Text")
    many2one_field=fields.Many2one("res.partner","Many2one")
