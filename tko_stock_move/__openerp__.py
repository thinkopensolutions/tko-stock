# -*- coding: utf-8 -*-
# © 2017 TKO <http://tko.tko-br.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Stock Move',
    'summary': '',
    'description': 'Mass transfer products from one location to another',
    'author': 'TKO',
    'category': 'Sale',
    'license': 'AGPL-3',
    'website': 'http://tko.tko-uk.com',
    'version': '10.0.0.0.0',
    'application': False,
    'installable': True,
    'auto_install': True,
    'depends': [
        'stock',
    ],
    'external_dependencies': {
        'python': [],
        'bin': [],
    },
    'init_xml': [],
    'update_xml': [
        'security/ir.model.access.csv',
        'views/stock_move_view.xml'],
    'css': [],
    'demo_xml': [],
    'test': [],
    'data': [],
}
