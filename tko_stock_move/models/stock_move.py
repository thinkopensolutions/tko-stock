# -*- coding: utf-8 -*-
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2017 ThinkOpen Solutions (<https://tkobr.com>).
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html


from openerp import models, fields, api, _
import time
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
from openerp.exceptions import Warning


class MassStockMove(models.Model):
    _name = 'mass.stock.move'
    _inherit = 'mail.thread'

    name = fields.Char(u'Name', required=True, readonly=True, states={'d': [('readonly', False)]},
                       track_visibility='onchange')
    date = fields.Datetime(u'Date', readonly=True)
    user_id = fields.Many2one('res.users', 'User', readonly=True, default=fields.Date.context_today)
    filter = fields.Selection([('a', 'Auto'), ('m', 'Manual Selection of Products')], required=True, default='a',
                              string='Filter', readonly=True, states={'d': [('readonly', False)]},
                              track_visibility='onchange')
    line_ids = fields.One2many('mass.stock.move.line', 'line_id', 'Products', readonly=True,
                               states={'d': [('readonly', False)]})
    state = fields.Selection([('d', u'Draft'), ('i', u'In Progress'), ('do', u'Done')], default='d', copy=False,
                             required=True, string=u'State', track_visibility='onchange')
    location_id = fields.Many2one('stock.location', u'Source  Location', required=True, readonly=True,
                                  states={'d': [('readonly', False)]}, track_visibility='onchange')
    location_dest_id = fields.Many2one('stock.location', u'Destination  Location', required=True, readonly=True,
                                       states={'d': [('readonly', False)]}, track_visibility='onchange')

    @api.constrains('location_id', 'location_dest_id')
    def _check_stock_move(self):
        if self.location_id == self.location_dest_id:
            raise Warning(u'Source and destination location can not be same')

    @api.multi
    def validate_inventory(self):
        stock_move = self.env['stock.move']
        for record in self:
            src_location_id = record.location_id.id
            location_dest_id = record.location_dest_id.id
            for line in self.line_ids:
                move = stock_move.create({
                    'name': record.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.theoretical_qty,
                    'product_uom': line.product_uom.id,
                    'location_id': src_location_id,
                    'location_dest_id': location_dest_id,
                    'company_id': record.location_id.company_id and record.location_id.company_id.id,
                    'invoice_state': 'none'
                })
                move.action_done()
                record.write({'state': 'do'})

        return True

    @api.multi
    def set_draft(self):
        self.write({'state': 'd'})

    @api.multi
    def prepare_inventory(self):
        mass_stock_move_line_obj = self.env['mass.stock.move.line']
        for inventory in self:
            # If there are inventory lines already (e.g. from import), respect those and set their theoretical qty
            line_ids = [line.id for line in inventory.line_ids]
            if not line_ids and inventory.filter == 'a':
                # compute the inventory lines and create them
                vals = inventory._get_inventory_lines()
                for product_line in vals:
                    if product_line['product_uom_qty'] > 1:
                        mass_stock_move_line_obj.create(product_line)
            if not len(inventory.line_ids):
                raise Warning(u'No lines to process')
        return self.write({'state': 'i', 'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})

    @api.multi
    def _get_inventory_lines(self):
        for inventory in self:
            location_obj = self.env['stock.location']
            product_obj = self.env['product.product']
            location_ids = location_obj.search([('id', 'child_of', [inventory.location_id.id])]).ids
            domain = ' location_id in %s'
            args = (tuple(location_ids),)

            self.env.cr.execute('''
               SELECT product_id, sum(qty) as product_uom_qty, location_id, lot_id as prod_lot_id, package_id, owner_id as partner_id
               FROM stock_quant WHERE''' + domain + '''
               GROUP BY product_id, location_id, lot_id, package_id, partner_id
            ''', args)
            vals = []
            for product_line in self.env.cr.dictfetchall():
                # replace the None the dictionary by False, because falsy values are tested later on
                for key, value in product_line.items():
                    if not value:
                        product_line[key] = False
                product_line['line_id'] = inventory.id
                #product_line['theoretical_qty'] = product_line['product_uom_qty']
                if product_line['product_id']:
                    product = product_obj.browse(product_line['product_id'])
                    product_line['product_uom'] = product.uom_id.id
                vals.append(product_line)
            return vals


class StockMove(models.Model):
    _name = 'mass.stock.move.line'

    product_uom_qty = fields.Float(u'Available Quantity', readonly=True)
    theoretical_qty = fields.Float(u'Transfer Quantity')
    product_uom = fields.Many2one('product.uom', u'UoM', readonly=True)

    product_id = fields.Many2one('product.product', u'Product', readonly=False)

    line_id = fields.Many2one('mass.stock.move', 'Move')

    @api.multi
    # get quantity on a location
    def _get_qty(self, product, location):
        result = product.with_context(location=location.id)._product_available(
            context=dict(self._context or {}, location=location.id, compute_child=False))
        qty_available = result[product.id].get('qty_available', 0.0)
        return qty_available

    # onchange doesn't work on readonly fields
    # write on record if we have id
    # creation we handle in create method
    @api.onchange('product_id')
    def product_id_change(self, product_id=False, location=False):
        if self.product_id:
            product = self.product_id
            qty_available = self._get_qty(product, self.line_id.location_id)
            self.product_uom = product.uom_id.id
            self.product_uom_qty = qty_available
            if len(self._origin):
                # write on the field
                self._origin.write({'product_uom': product.uom_id.id,
                                    'product_uom_qty': qty_available,
                                    })

        if product_id and location:
            result = {}
            product = self.env['product.product'].browse(product_id)
            qty_available = self._get_qty(product, location)
            result.update({'product_uom': product.uom_id.id,
                           'product_uom_qty': qty_available,
                           })
            return result

    @api.model
    def create(self, vals):
        if vals.get('product_id', False) and vals.get('line_id', False):
            move = self.env['mass.stock.move'].browse(vals['line_id'])
            location = move.location_id
            result = self.product_id_change(vals['product_id'], location)
            print "result......................", result, vals,
            vals.update(result)
        result = super(StockMove, self).create(vals)
        return result
