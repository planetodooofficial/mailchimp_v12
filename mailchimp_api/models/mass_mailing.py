from odoo import api,models,fields,_
from odoo.exceptions import UserError,Warning,ValidationError

class Mass_mailing_list(models.Model):
    _inherit = 'mail.mass_mailing.list'

    #Export List(Audience) and its Members in Mailchimp
    @api.multi
    def export_list_mailchimp(self):
        user = self.env.user
        partner = self.env.user.partner_id
        dict = {"name":partner.name,
                "company":user.company_id.name,
                "address1": partner.street,
                "address2": partner.street2,
                "city": partner.city,
                "state": partner.state_id.name,
                "zip": partner.zip,
                "country": partner.country_id.name,
                "phone": partner.phone,
                "from_name":partner.name,
                "email":partner.email,
                }
        try:
            list_id = self.env['mailchimp'].create_list(dict)
            return list_id
        except Exception as e:
            raise ValidationError(_("These are the Issues :%s") % e)

    #Update Members in List(Audience)
    @api.multi
    def update_list_mailchimp(self,list_id,ids):
        mc_email_lst = []
        odoo_email_lst = []
        mc_list_id = False
        mailchimp = self.env['mailchimp'].search([('name','=','Mailchimp')],limit=1)
        mailchimp.get_all_lists()
        for lines in mailchimp.list_lines:
            if lines.mailing_lists.ids == ids:
                mc_list_id = lines.mailchimp_list_id
        mc_list_record = self.env['mailchimp.lists'].search([('mailchimp_list_id','=',mc_list_id)])
        for memb_line in mc_list_record.members_line:
            mc_email_lst.append(memb_line.hash)
        for id in ids:
            mail_contacts = self.env['mail.mass_mailing.list_contact_rel'].search([('list_id', '=', id)])
            for contact in mail_contacts:
                user = self.env['mail.mass_mailing.contact'].browse(contact.contact_id.id)
                odoo_email_lst.append(user.email)
                if user.email not in mc_email_lst:
                    new_member =  mailchimp.createlist_members(list_id,user.name,user.email)
        for email in mc_email_lst:
            if email not in odoo_email_lst:
                del_memb = mailchimp.remove_member(list_id,email)

class Mass_mailing(models.Model):
    _inherit = 'mail.mass_mailing'

    exported = fields.Boolean('Exported')
    subject = fields.Char('Subject')
    use_mc_template = fields.Boolean('Use Mailchimp Templates')
    template_id = fields.Many2one('mailchimp.template','Template')

    @api.onchange('use_mc_template')
    def onchange_template_id(self):
        if self.use_mc_template:
            mailchimp = self.env['mailchimp'].search([('name','=','Mailchimp')],limit=1)
            mailchimp.get_all_templates()

    # To create a Campaign in mailchimp with its template
    @api.multi
    def send_to_mailchimp(self):

        data = {"html": self.body_html,
                "plain_text": "Template For Campaign :- %s" %self.name}
        list_audience = False
        error = []
        temp = 0
        mailchimp = self.env['mailchimp']
        try:
            name = self.env.user.name
            email = self.env.user.partner_id.email
            mc = self.env['mailchimp'].sudo().search([('name','=','Mailchimp')],limit=1)
            mc.get_all_lists()
            for lines in mc.list_lines:
                if lines.mailing_lists.ids == self.contact_list_ids.ids:
                    list_audience = lines.mailchimp_list_id
                    lines.get_members()
                    temp = 1
            if not list_audience:
                list = self.env['mail.mass_mailing.list'].export_list_mailchimp()
                list_audience = list["id"]
                for id in self.contact_list_ids.ids:
                    mail_contacts = self.env['mail.mass_mailing.list_contact_rel'].search([('list_id', '=',id)])
                    if mail_contacts:
                        for contact in mail_contacts:
                            try:
                                user = self.env['mail.mass_mailing.contact'].browse(contact.contact_id.id)
                                member = mailchimp.createlist_members(list["id"],user.name,user.email)
                            except Exception as exc:
                                error.append(exc.args[0])
            if temp==1:
                mail_list = self.env['mail.mass_mailing.list'].update_list_mailchimp(list_audience,self.contact_list_ids.ids)
            mc_template_id = False
            if self.use_mc_template:
                mc_template_id = self.template_id.mc_template_id
            campaign = mailchimp.create_campaign(self,data,name,email,list_audience,mc_template_id)
            if campaign:
                self.sudo().write({'exported':True})
                if temp==0:
                    history = self.env['mailchimp.lists'].sudo().create({'mailing_lists':[(6,0,self.contact_list_ids.ids)],
                                                              'mailchimp_list_id':list_audience,
                                                              'list_lines_id':mc.id})
                    history.get_members()
        except Exception as e:
            raise ValidationError(_("Error Occured with these contats : %s") % e.args[0])

