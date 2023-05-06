from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Quants(models.Model):
    _inherit = 'stock.quant'
    reserve_name = fields.Html(string="Отгрузки", help="Показывает на какие отгрузки зарезервирован продукт")
    available = fields.Float(string="Доступно", help="Доступное количество продукта", compute='_compute_available', store=True)
    how_much_is_reserved = fields.Float(string="Сколько зарезервировано", help="Показывает сколько товара зарезервировано", default=0)

    @api.depends('quantity')
    def _compute_available(self):
        for record in self:
            record.available = record.quantity

class First(models.Model):
    _inherit = 'picking.transport.info'
    where_to_take_from = fields.Char(string="Откуда брать", help="Показывает откуда брать продукт", default="")
    is_reserved = fields.Boolean(string="Зарезервировано", default=False)
    is_completed = fields.Boolean(string = 'Завершено ли полное комплектование', default=False)
    completion_status = fields.Selection(
        [('completed', 'Скомплектовано'), ('in-progress', 'В работе')],
        string = 'Статус комплектовки',
        description = 'Статус состояния комплектования',
        compute = '_completion_status_compute',
        store = True
    )

    @api.depends('completion_status', 'is_completed')
    def _completion_status_compute(self):
        for record in self:
            if record.is_completed == True:
                record.completion_status = 'completed'
            else:
                record.completion_status = 'in-progress'

    def reserve(self):
        if self.is_reserved == True:
            raise UserError("Уже зарезервировано")

        quants = self.env['stock.quant'].search([])
        products = {}
        where_to_take = {}

        for i in self.delivery_ids.move_ids_without_package:
            if i.product_id.default_code in products.keys():
                products[i.product_id.default_code] += i.product_uom_qty
            else:
                products[i.product_id.default_code] = i.product_uom_qty

        for i in self.delivery_ids.move_line_ids_without_package:
            if i.product_id.default_code in products.keys():
                products[i.product_id.default_code] += i.qty_done
            else:
                products[i.product_id.default_code] = i.qty_done

        for q in self.delivery_ids:
            path = q.location_id.id
            for i in quants:
                c = i.location_id.parent_path.split('/')
                local_path = list(filter(lambda x: x.strip(), c))
                if str(path) in local_path or i.location_id.id == q.location_id.id:
                            if i.product_id.default_code in products.keys() and i.available > 0:
                                if products[i.product_id.default_code] != 0:
                                    reserved_qty = min(products[i.product_id.default_code], i.available)
                                    products[i.product_id.default_code] -= reserved_qty
                                    i.how_much_is_reserved += reserved_qty
                                    move_link = f'<a href="/web#id={self.id}&view_type=form&model=picking.transport.info">{self.name}</a><br>'
                                    if i.reserve_name:
                                        if self.name not in i.reserve_name:
                                            i.reserve_name += move_link
                                    else:
                                        i.reserve_name = move_link
                                    i.available -= reserved_qty
                                    if i.product_id.name not in where_to_take:
                                        where_to_take[i.product_id.name] = []
                                    where_to_take[i.product_id.name].append((i.location_id.id, int(reserved_qty)))

        final_count = 0
        for number in products.values():
            final_count += number
        if final_count == 0:
            self.is_completed = True


        merged_data = {}
        for key, value in where_to_take.items():
            temp_dict = {}
            for v in value:
                if v[0] not in temp_dict:
                    temp_dict[v[0]] = v[1]
                else:
                    temp_dict[v[0]] += v[1]
            merged_data[key] = dict(temp_dict)

        end_count = {key: value for key, value in products.items() if value != 0}

        if set(products.keys()) == set(end_count.keys()):
            if all(products[k] == end_count[k] for k in end_count):
                raise UserError("Все товары отсутствуют на складе")

        self.where_to_take_from = merged_data

        end_end_count = {}
        for key, value in end_count.items():
            product_name = self.env['product.template'].search([('default_code', '=', key)])
            end_end_count[product_name.name] = value

        # for move_line in self.delivery_ids.move_line_ids_without_package:
        #     product_name = move_line.product_id.name
        #     if product_name in merged_data.keys():
        #         new_move_created = False
        #         for location, qty in merged_data[product_name].items():
        #             final_location = self.env['stock.location'].search([('id', '=', location)])
        #             if qty >= move_line.qty_done:
        #                 qty -= move_line.qty_done
        #                 move_line.location_id = final_location
        #             else:
        #                 new_move_qty = move_line.qty_done - qty
        #                 new_move_location_id = None
        #                 total_qty = 0
        #                 for next_location, next_qty in merged_data[product_name].items():
        #                     total_qty += next_qty
        #                     if next_location != location and next_qty >= new_move_qty:
        #                             new_move_location_id = self.env['stock.location'].search([('id', '=', next_location)])
        #                             new_move_created = True
        #                             break
        #                 if not new_move_created and total_qty >= new_move_qty:
        #                     new_move_location_id = self.env['stock.location'].search([('id', '=', location)])
        #
        #                 move_line.qty_done = new_move_qty
        #                 move_line.location_id = final_location
        #
        #                 new_move_vals = {
        #                     'name': move_line.product_id.name,
        #                     'product_id': move_line.product_id.id,
        #                     'product_uom_qty': new_move_qty,
        #                     'product_uom': move_line.product_id.uom_id.id,
        #                     'location_id': new_move_location_id.id,
        #                     'location_dest_id': location,
        #                     'picking_id': move_line.picking_id.id,
        #                 }

                        # new_move = self.env['stock.move'].sudo().create(new_move_vals)
                        # obj_list = [new_move]
                        # move_line.location_id = final_location
                        # obj_list.append(move_line)
                        # obj_list.reverse()
                        # for obj in obj_list:
                        #     obj.unlink()
                        # break


            for move_line in self.delivery_ids.move_ids_without_package:       # swap default location in record to actual location
                changed = False
                if product_name in merged_data.keys():
                    for location, qty in merged_data[product_name].items():
                        new_move_location_id = self.env['stock.location'].search(
                            [('id', '=', location)])
                        if qty >= move_line.product_uom_qty:
                            qty -= move_line.product_uom_qty
                            if move_line.move_line_ids:
                                    move_line.move_line_ids[0].write({'qty_done': 0, 'location_id': new_move_location_id, 'product_uom_qty': move_line.product_uom_qty,})
                                    changed = True
                            else:
                                new_move_vals = {
                                    'company_id': move_line.company_id.id,
                                    'location_id': new_move_location_id.id,
                                    'product_uom_qty': move_line.product_uom_qty,
                                    'product_uom_id': move_line.product_id.uom_id.id,
                                    'location_dest_id': move_line.location_dest_id.id,
                                    'qty_done': 0,
                                }
                                new_move_line = self.env['stock.move.line'].sudo().create(new_move_vals)
                                move_line.write({'move_line_ids': [(4, new_move_line.id)]})
                            break

                        else:
                            new_move_qty = move_line.product_uom_qty - qty
                            if move_line.move_line_ids and changed == False:
                                move_line.move_line_ids[0].write({'qty_done': 0, 'location_id': new_move_location_id, 'product_uom_qty': new_move_qty,})
                            else:
                                new_move_vals = {
                                    'company_id': move_line.company_id.id,
                                    'location_id': new_move_location_id.id,
                                    'product_uom_qty': new_move_qty,
                                    'product_uom_id': move_line.product_id.uom_id.id,
                                    'location_dest_id': move_line.location_dest_id.id,
                                    'qty_done': 0,
                                }
                                new_move_line = self.env['stock.move.line'].sudo().create(new_move_vals)
                                move_line.write({'move_line_ids': [(4, new_move_line.id)]})
                            qty = 0
                            for next_location, next_qty in merged_data[product_name].items():
                                if next_location != location and new_move_qty > 0 and next_qty > 0:
                                    new_move_location_id = self.env['stock.location'].search(
                                        [('id', '=', next_location)])
                                    if move_line.move_line_ids:
                                        move_line.move_line_ids[0].write(
                                            {'qty_done': 0, 'location_id': new_move_location_id,
                                             'product_uom_qty': new_move_qty, })
                                    else:
                                        new_move_vals = {
                                            'company_id': move_line.company_id.id,
                                            'location_id': new_move_location_id.id,
                                            'product_uom_qty': min(new_move_qty, next_qty),
                                            'product_uom_id': move_line.product_id.uom_id.id,
                                            'location_dest_id': move_line.location_dest_id.id,
                                            'qty_done': 0,
                                        }
                                        new_move_line = self.env['stock.move.line'].sudo().create(new_move_vals)
                                        move_line.write({'move_line_ids': [(4, new_move_line.id)]})
                                        new_move_qty -= next_qty
                                        new_move_qty = max(new_move_qty, 0)
                                        next_qty = min(new_move_qty - next_qty, 0)


            # obj_list = []
            # move_line.location_id = final_location
            # obj_list.append(move_line)
            # obj_list.reverse()
            # for obj in obj_list:
            #     obj.unlink()
            # break



        self.is_reserved = True

        merged_merged_data = merged_data
        for key, value in merged_merged_data.items():
            for location_id, qty in value.items():
                final_location = self.env['stock.location'].search([('id', '=', location_id)])
                location = final_location.name_get()[0][1]
                merged_data[key][location_id] = location


        if end_count:
            merged_format = str(merged_merged_data).replace('{', '').replace('}', '').replace('[', '').replace(']', '').replace('\'','').replace('(', '').replace(')', '')
            end_count_format = str(end_end_count).replace('{', '').replace('}', '').replace('[', '').replace(']', '').replace('\'', '').replace('(', '').replace(')', '')
            self.env['mail.message'].sudo().create({
                'subject': 'Резервирование',
                'body': 'Зарезервированы продукты на складе: {} \n Не хватает на складе: {}'.format(merged_format, end_count_format),
                'model': self._name,
                'res_id': self.id,
                'message_type': 'notification',
                'subtype_id': self.env.ref('mail.mt_comment').id,
            })
        else:
            merged_format = str(merged_data).replace('{', '').replace('}', '').replace('[', '').replace(']', '').replace('\'','').replace('(', '').replace(')', '')
            self.env['mail.message'].sudo().create({
            'subject': 'Резервирование',
            'body': 'Зарезервированы продукты на складе: {}'.format(merged_format),
            'model': self._name,
            'res_id': self.id,
            'message_type': 'notification',
            'subtype_id': self.env.ref('mail.mt_comment').id,
            })


        return {
            'effect': {
                'fadeout': 'slow',
                'message': 'Успешно зарезервировано',
                'type': 'rainbow_man',
            }
        }


    def reserve_cancel(self):
        if not self.where_to_take_from:
            raise UserError("Нет резервирования для снятия")
        quants = self.env['stock.quant'].search([])
        dicc = eval(self.where_to_take_from)
        self.is_reserved = False


        for i in self.delivery_ids.move_line_ids_without_package:
            i.location_id = i.location_id

        for product_name, locations in dicc.items():
            for location_id, qty in locations.items():
                reserved_quants = quants.filtered(lambda x: x.product_id.name == product_name and x.location_id.id == location_id and x.how_much_is_reserved > 0)
                if reserved_quants:
                    reserved_qty = min(qty, sum(reserved_quants.mapped('how_much_is_reserved')))
                    for quant in reserved_quants:
                        if reserved_qty <= 0:
                            break
                        if reserved_qty < quant.how_much_is_reserved:
                            quant.how_much_is_reserved -= reserved_qty
                            quant.available += reserved_qty
                            reserved_qty = 0
                        else:
                            reserved_qty -= quant.how_much_is_reserved
                            quant.available += quant.how_much_is_reserved
                            quant.how_much_is_reserved = 0
                            move_link = f'<a href="/web#id={self.id}&view_type=form&model=picking.transport.info">{self.name}</a><br>'
                            if quant.reserve_name and move_link in quant.reserve_name:
                                quant.reserve_name = quant.reserve_name.replace(self.name, '')

        self.where_to_take_from = None

        self.is_completed = False

        self.env['mail.message'].sudo().create({
            'subject': 'Снятие резервирования',
            'body': 'Снятие резервирования',
            'model': self._name,
            'res_id': self.id,
            'message_type': 'notification',
            'subtype_id': self.env.ref('mail.mt_comment').id,
        })

        return {
            'effect': {
                'fadeout': 'slow',
                'message': 'Резервирование снято',
                'type': 'rainbow_man',
            }
        }

