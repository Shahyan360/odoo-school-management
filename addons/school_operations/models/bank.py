import hashlib
import json
import os
import re
import time
from odoo import api,fields,models
from odoo.exceptions import AccessError,UserError,ValidationError
from psycopg2.errors import UniqueViolation
from ..common import guard,signature_ok,decimal

class Adapter(models.Model):
    _name='school.bank.adapter'
    _description='Generic Fictional Bank Adapter Configuration'
    _rec_name='code'
    code=fields.Char(required=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    secret_env=fields.Char(required=True,default='LAB_BANK_SECRET')
    journal_id=fields.Many2one('account.journal',required=True,domain=[('type','in',['bank','cash'])],check_company=True)
    service_user_id=fields.Many2one('res.users',required=True,default=lambda s:s.env.user)
    active=fields.Boolean(default=True)
    _sql_constraints=[('code_unique','unique(code)','Adapter code must be unique.')]
    @api.constrains('code','service_user_id','journal_id','secret_env')
    def _check(self):
        for a in self:
            if not re.fullmatch(r'[a-z0-9-]+',a.code or '') or not re.fullmatch(r'[A-Z][A-Z0-9_]*',a.secret_env or ''):
                raise ValidationError('Use a URL-safe code and uppercase environment variable name.')
            if a.company_id not in a.service_user_id.company_ids or a.journal_id.company_id!=a.company_id:
                raise ValidationError('Service user and journal must be authorized for the adapter company.')

class Receipt(models.Model):
    _name='school.bank.receipt'
    _description='Authenticated Generic Bank Receipt'
    adapter_id=fields.Many2one('school.bank.adapter',required=True,ondelete='restrict')
    company_id=fields.Many2one(related='adapter_id.company_id',store=True)
    txid=fields.Char(required=True,index=True)
    source_hash=fields.Char(required=True)
    invoice_id=fields.Many2one('account.move',required=True,check_company=True)
    currency_id=fields.Many2one('res.currency',required=True)
    amount=fields.Monetary(required=True)
    payment_date=fields.Date(required=True)
    provider_status=fields.Selection([('success','Success'),('failed','Failed')],required=True)
    state=fields.Selection([('pending','Pending Review'),('applied','Applied'),('failed','Failed')],default='pending',readonly=True)
    payment_ids=fields.Many2many('account.payment',readonly=True)
    error=fields.Text(readonly=True)
    _sql_constraints=[('tx_unique','unique(adapter_id,txid)','Transaction already recorded.')]
    @api.model_create_multi
    def create(self,vals_list):
        raise AccessError('Receipt source records are created only through the signed bank entry point.')
    def write(self,vals):
        if {'state','payment_ids','txid','source_hash','invoice_id','amount','currency_id','payment_date','provider_status','adapter_id'}.intersection(vals):
            raise AccessError('Bank receipt source and application state are controlled by the adapter.')
        return super().write(vals)

    @api.model
    def _receive(self,adapter,raw,signature):
        if len(raw)>65536 or not adapter.active or not signature_ok(os.environ.get(adapter.secret_env),raw,signature):
            raise AccessError('Request signature was rejected.')
        try:
            data=json.loads(raw)
            if not isinstance(data,dict): raise ValueError('Expected a JSON object')
            stamp=int(data['timestamp'])
            payment_date=fields.Date.to_date(data['date'])
            if not payment_date: raise ValueError('Date is required')
        except (ValueError,TypeError,KeyError,AttributeError):
            raise ValidationError('Invalid signed callback structure.')
        if abs(time.time()-stamp)>300:
            raise ValidationError('Signed callback timestamp is outside the five-minute replay window.')
        txid=str(data.get('transaction_id',''))
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',txid):
            raise ValidationError('Invalid transaction identifier.')
        existing=self.search([('adapter_id','=',adapter.id),('txid','=',txid)],limit=1)
        digest=hashlib.sha256(raw).hexdigest()
        if existing:
            if existing.source_hash!=digest:
                raise ValidationError('Transaction identifier was reused for different signed content.')
            return existing
        invoices=self.env['account.move'].search([('company_id','=',adapter.company_id.id),
            ('name','=',str(data.get('invoice_reference',''))),('state','=','posted'),('move_type','=','out_invoice')],limit=2)
        if len(invoices)!=1 or not invoices.school_student_id:
            raise ValidationError('The referenced posted operational invoice is not accessible.')
        currency=self.env['res.currency'].search([('name','=',str(data.get('currency','')))],limit=1)
        if currency!=invoices.currency_id or data.get('status') not in ('success','failed'):
            raise ValidationError('Currency or provider status does not match the supported callback contract.')
        amount=decimal(data.get('amount'))
        if amount<=0:
            raise ValidationError('Payment amount must be positive.')
        try:
            with self.env.cr.savepoint():
                return super(Receipt,self).create({'adapter_id':adapter.id,'txid':txid,'source_hash':digest,
                    'invoice_id':invoices.id,'currency_id':currency.id,'amount':float(amount),
                    'provider_status':data['status'],'payment_date':payment_date})
        except UniqueViolation:
            receipt=self.search([('adapter_id','=',adapter.id),('txid','=',txid)],limit=1)
            if receipt.source_hash!=digest:
                raise ValidationError('Conflicting repeated payment callback.')
            return receipt

    def action_apply(self):
        guard(self,'school_operations.group_accounts')
        for receipt in self:
            if receipt.state=='applied': continue
            if receipt.provider_status=='failed':
                super(Receipt,receipt).write({'state':'failed','error':'Provider reported a failed payment.'})
                continue
            receipt.invoice_id.check_access_rule('write')
            self.env.cr.execute('SELECT id FROM account_move WHERE id=%s FOR UPDATE',(receipt.invoice_id.id,))
            receipt.invoice_id.invalidate_recordset()
            if receipt.invoice_id.state!='posted' or receipt.currency_id.compare_amounts(receipt.amount,receipt.invoice_id.amount_residual)>0:
                raise UserError('Amount exceeds current residual or invoice is not posted. Review any advance separately.')
            register=self.env['account.payment.register'].with_context(active_model='account.move',active_ids=receipt.invoice_id.ids).create({
                'amount':receipt.amount,'payment_date':receipt.payment_date,'journal_id':receipt.adapter_id.journal_id.id,
                'communication':receipt.txid,'payment_difference_handling':'open'})
            payments=register._create_payments()
            super(Receipt,receipt).write({'payment_ids':[(6,0,payments.ids)],'state':'applied','error':False})
        return True
