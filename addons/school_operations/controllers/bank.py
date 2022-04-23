from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError,ValidationError,UserError

class BankCallback(http.Controller):
    @http.route('/lab/school/bank/<string:code>',type='http',auth='public',methods=['POST'],csrf=False,save_session=False)
    def callback(self,code,**kwargs):
        if request.httprequest.content_length and request.httprequest.content_length>65536:
            return request.make_json_response({'error':'payload too large'},status=413)
        adapter=request.env['school.bank.adapter'].sudo().search([('code','=',code),('active','=',True)],limit=1)
        if not adapter: return request.not_found()
        receipts=request.env['school.bank.receipt'].with_user(adapter.service_user_id).with_company(adapter.company_id)
        try:
            receipt=receipts._receive(adapter.with_user(adapter.service_user_id),request.httprequest.get_data(),request.httprequest.headers.get('X-Lab-Signature'))
        except AccessError:
            return request.make_json_response({'error':'signature or access rejected'},status=401)
        except (ValidationError,UserError):
            return request.make_json_response({'error':'invalid callback or invoice mapping'},status=400)
        return request.make_json_response({'accepted':True,'receipt':receipt.id,'state':receipt.state},status=202)
