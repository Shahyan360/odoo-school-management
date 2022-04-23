from datetime import date
from odoo import api,fields,models,Command
from odoo.exceptions import AccessError,UserError,ValidationError
from ..common import guard

class Campus(models.Model):
    _name='school.campus'
    _description='Fictional School Campus'
    name=fields.Char(required=True)
    code=fields.Char(required=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    active=fields.Boolean(default=True)
    _sql_constraints=[('code_unique','unique(company_id,code)','Campus code must be unique per company.')]

class Session(models.Model):
    _name='school.session'
    _description='Academic Session'
    name=fields.Char(required=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    date_start=fields.Date(required=True)
    date_end=fields.Date(required=True)
    @api.constrains('date_start','date_end')
    def _dates(self):
        if any(s.date_end<s.date_start for s in self): raise ValidationError('Academic end date precedes its start.')

class Grade(models.Model):
    _name='school.grade'
    _description='School Grade'
    name=fields.Char(required=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)

class Section(models.Model):
    _name='school.section'
    _description='Campus Grade Section'
    _check_company_auto=True
    name=fields.Char(required=True)
    campus_id=fields.Many2one('school.campus',required=True,check_company=True)
    company_id=fields.Many2one(related='campus_id.company_id',store=True)
    grade_id=fields.Many2one('school.grade',required=True,check_company=True)

class Users(models.Model):
    _inherit='res.users'
    school_campus_ids=fields.Many2many('school.campus',string='Authorized School Campuses')
    def write(self,vals):
        if 'school_campus_ids' in vals and not self.env.user.has_group('school_operations.group_manager'):
            raise AccessError('Only school administrators assign campus permissions.')
        return super().write(vals)

class Employee(models.Model):
    _inherit='hr.employee'
    school_campus_id=fields.Many2one('school.campus',check_company=True)

class Application(models.Model):
    _name='school.application'
    _description='School Admission Application'
    _inherit=['mail.thread','mail.activity.mixin']
    _check_company_auto=True
    name=fields.Char(required=True,default='New',readonly=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    campus_id=fields.Many2one('school.campus',required=True,check_company=True)
    student_name=fields.Char(required=True)
    date_of_birth=fields.Date(required=True)
    guardian_id=fields.Many2one('res.partner',required=True,check_company=True)
    session_id=fields.Many2one('school.session',required=True,check_company=True)
    grade_id=fields.Many2one('school.grade',required=True,check_company=True)
    section_id=fields.Many2one('school.section',required=True,check_company=True)
    document_ids=fields.One2many('school.application.document','application_id')
    student_id=fields.Many2one('school.student',readonly=True)
    state=fields.Selection([(s,s.title()) for s in ('inquiry','application','review','accepted','enrolled')],default='inquiry',readonly=True,tracking=True)
    note=fields.Text()
    _sql_constraints=[('admission_unique','unique(company_id,name)','Admission reference must be unique.')]

    @api.model_create_multi
    def create(self,vals_list):
        for vals in vals_list:
            if vals.get('state','inquiry')!='inquiry' or vals.get('student_id'):
                raise AccessError('Start with an admission inquiry.')
            vals['name']=self.env['ir.sequence'].next_by_code('school.application')
        return super().create(vals_list)
    def write(self,vals):
        if {'state','student_id'}.intersection(vals): raise AccessError('Use admission workflow actions.')
        if any(r.state=='enrolled' for r in self) and {'student_name','date_of_birth','guardian_id','campus_id','grade_id','section_id','session_id'}.intersection(vals):
            raise UserError('Update the enrolled student through controlled student records.')
        return super().write(vals)
    @api.constrains('section_id','grade_id','campus_id','date_of_birth')
    def _valid(self):
        for r in self:
            if r.section_id.campus_id!=r.campus_id or r.section_id.grade_id!=r.grade_id or r.date_of_birth>=fields.Date.context_today(r):
                raise ValidationError('Section/campus/grade and date of birth must be consistent.')
    def _step(self,source,target):
        guard(self,'school_operations.group_admissions')
        for r in self:
            if r.state!=source: raise UserError('Admission stage is out of sequence.')
            if target=='accepted' and (not r.document_ids or any(d.required and not d.received for d in r.document_ids)):
                raise UserError('Complete the required admission document checklist.')
            super(Application,r).write({'state':target})
            r.message_post(body='Admission moved to '+target+'.')
        return True
    def action_apply(self): return self._step('inquiry','application')
    def action_review(self): return self._step('application','review')
    def action_accept(self): return self._step('review','accepted')
    def action_enroll(self):
        guard(self,'school_operations.group_admissions')
        for r in self:
            if r.student_id: continue
            if r.state!='accepted': raise UserError('Accept the application before enrollment.')
            student=self.env['school.student'].create({'name':r.student_name,'date_of_birth':r.date_of_birth,
                'guardian_id':r.guardian_id.id,'company_id':r.company_id.id,'campus_id':r.campus_id.id,
                'session_id':r.session_id.id,'grade_id':r.grade_id.id,'section_id':r.section_id.id})
            student._record_enrollment()
            super(Application,r).write({'student_id':student.id,'state':'enrolled'})
        return True

class Document(models.Model):
    _name='school.application.document'
    _description='Admission Document Checklist'
    application_id=fields.Many2one('school.application',required=True,ondelete='cascade')
    campus_id=fields.Many2one(related='application_id.campus_id',store=True)
    company_id=fields.Many2one(related='application_id.company_id',store=True)
    name=fields.Char(required=True)
    required=fields.Boolean(default=True)
    received=fields.Boolean(default=False)
    attachment_id=fields.Many2one('ir.attachment')

class Student(models.Model):
    _name='school.student'
    _description='Private School Student Record'
    _inherit=['mail.thread']
    _check_company_auto=True
    name=fields.Char(required=True)
    admission_number=fields.Char(readonly=True,copy=False,required=True,default='New')
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    campus_id=fields.Many2one('school.campus',required=True,check_company=True)
    date_of_birth=fields.Date(required=True)
    guardian_id=fields.Many2one('res.partner',required=True,check_company=True)
    session_id=fields.Many2one('school.session',required=True,check_company=True)
    grade_id=fields.Many2one('school.grade',required=True,check_company=True)
    section_id=fields.Many2one('school.section',required=True,check_company=True)
    active=fields.Boolean(default=True)
    status=fields.Selection([('enrolled','Enrolled'),('withdrawn','Withdrawn'),('graduated','Graduated')],default='enrolled')
    enrollment_ids=fields.One2many('school.enrollment','student_id',readonly=True)
    transfer_section_id=fields.Many2one('school.section',check_company=True)
    currency_id=fields.Many2one(related='company_id.currency_id')
    balance=fields.Monetary(compute='_compute_balance',groups='school_operations.group_accounts')
    _sql_constraints=[('student_number_unique','unique(company_id,admission_number)','Admission number already exists.'),
        ('student_identity_unique','unique(company_id,name,date_of_birth,guardian_id)','Possible duplicate student: review identity and guardian.')]
    @api.model_create_multi
    def create(self,vals_list):
        for vals in vals_list: vals['admission_number']=self.env['ir.sequence'].next_by_code('school.student')
        return super().create(vals_list)
    def write(self,vals):
        if {'campus_id','session_id','grade_id','section_id','admission_number'}.intersection(vals):
            raise AccessError('Use the controlled section-transfer action.')
        return super().write(vals)
    def _record_enrollment(self):
        for s in self:
            self.env['school.enrollment'].create({'student_id':s.id,'campus_id':s.campus_id.id,
                'session_id':s.session_id.id,'grade_id':s.grade_id.id,'section_id':s.section_id.id,'date_start':fields.Date.context_today(s)})
    def action_transfer(self):
        guard(self,'school_operations.group_manager')
        for s in self:
            section=s.transfer_section_id
            if not section or section.company_id!=s.company_id: raise UserError('Select a destination section in the same company.')
            s.enrollment_ids.filtered(lambda e:not e.date_end).write({'date_end':fields.Date.context_today(s)})
            super(Student,s).write({'campus_id':section.campus_id.id,'grade_id':section.grade_id.id,'section_id':section.id,'transfer_section_id':False})
            s._record_enrollment()
            s.message_post(body='Student transferred through a controlled enrollment action.')
        return True
    def _compute_balance(self):
        for s in self:
            s.balance=sum(self.env['account.move'].search([('school_student_id','=',s.id),('state','=','posted')]).mapped('amount_residual_signed'))

class Enrollment(models.Model):
    _name='school.enrollment'
    _description='Student Enrollment History'
    student_id=fields.Many2one('school.student',required=True,ondelete='restrict')
    company_id=fields.Many2one(related='student_id.company_id',store=True)
    campus_id=fields.Many2one('school.campus',required=True)
    session_id=fields.Many2one('school.session',required=True)
    grade_id=fields.Many2one('school.grade',required=True)
    section_id=fields.Many2one('school.section',required=True)
    date_start=fields.Date(required=True)
    date_end=fields.Date()

class FeePlan(models.Model):
    _name='school.fee.plan'
    _description='Campus Grade Fee Schedule'
    _check_company_auto=True
    name=fields.Char(required=True)
    campus_id=fields.Many2one('school.campus',required=True)
    company_id=fields.Many2one(related='campus_id.company_id',store=True)
    session_id=fields.Many2one('school.session',required=True,check_company=True)
    grade_id=fields.Many2one('school.grade',required=True,check_company=True)
    currency_id=fields.Many2one(related='company_id.currency_id')
    discount_percent=fields.Float(default=0)
    line_ids=fields.One2many('school.fee.plan.line','plan_id')
    _sql_constraints=[('schedule_unique','unique(campus_id,session_id,grade_id)','One fee schedule per campus, session and grade.')]
    @api.constrains('discount_percent')
    def _check(self):
        if any(not 0<=p.discount_percent<=100 for p in self): raise ValidationError('Discount must be 0 to 100 percent.')

class FeeLine(models.Model):
    _name='school.fee.plan.line'
    _description='School Fee Category'
    plan_id=fields.Many2one('school.fee.plan',required=True,ondelete='cascade')
    campus_id=fields.Many2one(related='plan_id.campus_id',store=True)
    company_id=fields.Many2one(related='plan_id.company_id',store=True)
    currency_id=fields.Many2one(related='company_id.currency_id')
    name=fields.Char(required=True)
    product_id=fields.Many2one('product.product',required=True)
    amount=fields.Monetary(required=True)
    recurrence=fields.Selection([('monthly','Monthly'),('admission','One-time Admission'),('annual','Annual')],default='monthly',required=True)
    @api.constrains('amount')
    def _check(self):
        if any(l.amount<0 for l in self): raise ValidationError('Fee amounts cannot be negative.')

class FeePeriod(models.Model):
    _name='school.fee.period'
    _description='Monthly Fee Generation Batch'
    name=fields.Char(required=True,default='Fee Batch')
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    campus_id=fields.Many2one('school.campus',required=True,check_company=True)
    period=fields.Date(required=True,default=lambda s:fields.Date.context_today(s).replace(day=1))
    generated_invoice_ids=fields.Many2many('account.move',readonly=True)
    def action_generate(self):
        guard(self,'school_operations.group_accounts')
        for batch in self:
            if batch.period.day!=1: raise UserError('Select the first day of the billing month.')
            students=self.env['school.student'].search([('campus_id','=',batch.campus_id.id),('status','=','enrolled'),('active','=',True)])
            for student in students:
                guard(student,'school_operations.group_accounts',operation='read')
                plan=self.env['school.fee.plan'].search([('campus_id','=',student.campus_id.id),('session_id','=',student.session_id.id),('grade_id','=',student.grade_id.id)],limit=1)
                if not plan: raise UserError('No fee plan exists for '+student.admission_number)
                if not student.session_id.date_start<=batch.period<=student.session_id.date_end:
                    continue
                due=[]
                for line in plan.line_ids:
                    cycle=batch.period.strftime('%Y-%m') if line.recurrence=='monthly' else str(batch.period.year) if line.recurrence=='annual' else 'admission'
                    if not self.env['school.fee.charge'].search_count([('student_id','=',student.id),('fee_line_id','=',line.id),('cycle','=',cycle)]):
                        due.append((line,cycle))
                if not due: continue
                invoice=self.env['account.move'].with_company(batch.company_id).create({
                    'move_type':'out_invoice','partner_id':student.guardian_id.id,'company_id':batch.company_id.id,
                    'invoice_date':batch.period,'school_student_id':student.id,'school_campus_id':student.campus_id.id,
                    'invoice_line_ids':[Command.create({'product_id':line.product_id.id,'name':line.name+' - '+student.admission_number,
                        'quantity':1,'price_unit':line.amount,'discount':plan.discount_percent}) for line,cycle in due]})
                for line,cycle in due:
                    self.env['school.fee.charge'].create({'student_id':student.id,'fee_line_id':line.id,'cycle':cycle,'invoice_id':invoice.id})
                batch.generated_invoice_ids=[Command.link(invoice.id)]
        return True
    @api.model
    def _cron_generate(self):
        today=fields.Date.context_today(self).replace(day=1)
        for campus in self.env['school.campus'].search([('active','=',True)]):
            batch=self.search([('campus_id','=',campus.id),('period','=',today)],limit=1)
            if not batch: batch=self.create({'company_id':campus.company_id.id,'campus_id':campus.id,'period':today})
            batch.action_generate()

class Charge(models.Model):
    _name='school.fee.charge'
    _description='Idempotent Student Fee Charge'
    student_id=fields.Many2one('school.student',required=True,ondelete='restrict')
    campus_id=fields.Many2one(related='student_id.campus_id',store=True)
    company_id=fields.Many2one(related='student_id.company_id',store=True)
    fee_line_id=fields.Many2one('school.fee.plan.line',required=True,ondelete='restrict')
    cycle=fields.Char(required=True)
    invoice_id=fields.Many2one('account.move',required=True,ondelete='restrict')
    _sql_constraints=[('charge_unique','unique(student_id,fee_line_id,cycle)','This fee charge already exists for the billing cycle.')]
    def write(self,vals): raise AccessError('Fee charge history cannot be changed; use a native credit note for corrections.')

class Move(models.Model):
    _inherit='account.move'
    school_student_id=fields.Many2one('school.student',check_company=True,copy=True,index=True)
    school_campus_id=fields.Many2one('school.campus',check_company=True,copy=True,index=True)

class PurchaseRequest(models.Model):
    _name='school.purchase.request'
    _description='Campus Administrative Purchase Request'
    name=fields.Char(required=True)
    campus_id=fields.Many2one('school.campus',required=True)
    company_id=fields.Many2one(related='campus_id.company_id',store=True)
    product_id=fields.Many2one('product.product',required=True)
    quantity=fields.Float(default=1,required=True)
    vendor_id=fields.Many2one('res.partner',required=True)
    requester_id=fields.Many2one('res.users',default=lambda s:s.env.user,readonly=True)
    state=fields.Selection([('draft','Draft'),('submitted','Submitted'),('approved','Approved'),('ordered','RFQ Created')],default='draft',readonly=True)
    purchase_id=fields.Many2one('purchase.order',readonly=True)
    @api.model_create_multi
    def create(self,vals_list):
        if not self.env.user.has_group('school_operations.group_user'):
            raise AccessError('School staff access is required.')
        for vals in vals_list:
            if vals.get('state','draft')!='draft' or vals.get('purchase_id') or vals.get('requester_id',self.env.uid)!=self.env.uid:
                raise AccessError('Create your own draft request; use the review actions for approval.')
            vals['requester_id']=self.env.uid
        return super().create(vals_list)
    def write(self,vals):
        if {'state','purchase_id','requester_id'}.intersection(vals): raise AccessError('Use purchase request actions.')
        if any(r.state!='draft' for r in self) and {'quantity','product_id','vendor_id','campus_id'}.intersection(vals):
            raise UserError('Reviewed purchase request terms cannot be changed.')
        return super().write(vals)
    def action_submit(self):
        guard(self,'school_operations.group_user')
        for r in self:
            if r.state!='draft' or r.quantity<=0: raise UserError('Submit a draft with a positive quantity.')
            super(PurchaseRequest,r).write({'state':'submitted'})
        return True
    def action_approve(self):
        guard(self,'school_operations.group_campus_manager')
        for r in self:
            if r.state!='submitted' or r.requester_id==self.env.user: raise UserError('An independent campus manager must review the submitted request.')
            super(PurchaseRequest,r).write({'state':'approved'})
        return True
    def action_order(self):
        guard(self,'school_operations.group_campus_manager')
        for r in self:
            if r.purchase_id: continue
            if r.state!='approved': raise UserError('Approve the request first.')
            po=self.env['purchase.order'].create({'partner_id':r.vendor_id.id,'company_id':r.company_id.id,'origin':r.name,
                'order_line':[Command.create({'product_id':r.product_id.id,'product_qty':r.quantity,'price_unit':r.product_id.standard_price})]})
            super(PurchaseRequest,r).write({'state':'ordered','purchase_id':po.id})
        return True
