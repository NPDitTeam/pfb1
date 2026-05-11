
from odoo import api, fields, models,_
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError




class PartnerCategory(models.Model):
    _name = 'partner.category'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Partner Category'
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name DESC'

    name = fields.Char('Category Name Partner',index=True,required=True)
    parent_id =  fields.Many2one('partner.category', string='Parent Partner Category',index=True, ondelete='cascade')
    prefix_category_partner = fields.Char('Prefix Category Partner',required=True)
    parent_path = fields.Char(index=True)
    child_id = fields.One2many('partner.category', 'parent_id', 'Child Categories')
    type_category = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Supplier'),
    ], string='Type Category',default='customer',required=True)
    code = fields.Char('Code',required=True)
    complete_name = fields.Char(
        'Complete Name',
        compute='_compute_complete_name',
        store=True)
    partner_count = fields.Integer(
        '# Partners', compute='_compute_partner_count',
        )
    sequence_id = fields.Many2one('ir.sequence', string='Sequence')

    @api.model
    def create(self, values):
        if not values.get('sequence_id'):
            seq_id = self.env['ir.sequence'].create({
                'name': values.get('prefix_category_partner') + '-' +values.get('type_category'),
                'code':'partner.partner' + '-' + values.get('prefix_category_partner') ,
                'prefix':values.get('prefix_category_partner') +'-'
            })
            values['sequence_id'] = seq_id.id
        return super().create(values)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
            for category in self:
                if category.parent_id:
                    category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
                else:
                    category.complete_name = category.name

    def _compute_partner_count(self):
        read_group_res = self.env['res.partner'].read_group([('partner_cate_id', 'child_of', self.ids)], ['partner_cate_id'], ['partner_cate_id'])
        group_data = dict((data['partner_cate_id'][0], data['partner_cate_id_count']) for data in read_group_res)
        for categ in self:
            partner_count = 0
            for sub_categ_id in categ.search([('id', 'child_of', categ.ids)]).ids:
                partner_count += group_data.get(sub_categ_id, 0)
            categ.partner_count = partner_count


class Partner(models.Model):
    _inherit = 'res.partner'

    partner_cate_id = fields.Many2one('partner.category', string='Partner Category')
    partner_cate_list = fields.Many2many(comodel_name="partner.category",string="Cate List",compute='_get_list_partner_cate')

    @api.depends('customer','supplier')
    def _get_list_partner_cate(self):
        partner_cate = self.env['partner.category']
        for pt in self:
            if pt.customer and pt.supplier:
                pt.partner_cate_list =partner_cate.search([('type_category','in',['customer','supplier'])]).ids
            elif pt.customer:
                pt.partner_cate_list =  partner_cate.search([('type_category','=','customer')]).ids
            elif pt.supplier:
                pt.partner_cate_list =  partner_cate.search([('type_category','=','supplier')]).ids
            else:
                pt.partner_cate_list =  None
    
    @api.model
    def create(self, values):
        if values.get('partner_cate_id') and not values.get('ref'):
            partner_cate = self.env['partner.category'].browse([values.get('partner_cate_id')])
            values['ref'] = partner_cate.sequence_id.next_by_id()
        return super().create(values)

    def write(self, values):
        if any(field in values for field in ['partner_cate_id']): 
            for record in self:
                if not record.ref:
                    partner_cate = record.env['partner.category'].browse([values.get('partner_cate_id')])
                    values['ref'] = partner_cate.sequence_id.next_by_id()
        return super().write(values)
