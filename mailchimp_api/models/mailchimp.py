from mailchimp3 import MailChimp
from odoo import fields,api,models,_
from odoo.exceptions import Warning,UserError,ValidationError

class Mailchimp_templates(models.Model):
    _name = 'mailchimp.template'

    name = fields.Char('Name')
    mc_template_id = fields.Integer('Template-ID')

class Mailchimp_members(models.Model):
    _name = 'mailchimp.lists.members'

    hash = fields.Char('Subscriber Hash')
    member_id = fields.Char('Members-ID')
    mc_list = fields.Char('List-ID')
    mc_list_id = fields.Many2one('mailchimp.lists')

class Mailchimp_lists(models.Model):
    _name = 'mailchimp.lists'

    members_line = fields.One2many('mailchimp.lists.members','mc_list_id','Members')
    list_lines_id = fields.Many2one('mailchimp')
    mailing_lists = fields.Many2many('mail.mass_mailing.list','mailchimp_lists_rel','mailchimp_list_id','mailing_list_id')
    mailchimp_list_id = fields.Char('Mailchimp List')

    @api.multi
    def unlink(self):
        for lines in self.members_line:
            lines.unlink()
        return super(Mailchimp_lists,self).unlink()

    @api.multi
    def get_members(self):
        try:
            members = self.env['mailchimp'].get_members_all(self.mailchimp_list_id)
            mc_mem_list = []
            for email in members["members"]:
                mc_mem_list.append(email["email_address"])
            for contacts in members["members"]:
                mc_memb = self.env['mailchimp.lists.members'].search([('member_id','=',contacts["id"]),('mc_list','=',self.mailchimp_list_id)])
                if not mc_memb:
                    vals = {'hash': contacts["email_address"],
                            'member_id': contacts["id"],
                            'mc_list_id': self.id,
                            'mc_list': contacts["list_id"]}
                    memb = self.env['mailchimp.lists.members'].create(vals)
            for lines in self.members_line:
                if lines.hash not in mc_mem_list:
                    del_record = lines.unlink()
        except Exception as e:
            raise ValidationError(_("Something Went Wrong : %s") % e)

class Mailchimp(models.Model):
    _name = 'mailchimp'

    api_key = fields.Char('Mailchimp Key')
    api_email = fields.Char('Mailchimp Email')
    name = fields.Char('Name',default='Mailchimp')
    list_lines = fields.One2many('mailchimp.lists','list_lines_id','Lists')

    #To test connection of odoo and Mailchimp
    @api.multi
    def test_connection(self):
        client  = self.mailchimp_connect()
        # del_memb = client.lists.members.delete(list_id='d59960aa3a', subscriber_hash='ketal.planetodoo@gmail.com')
        # a=1
        # a = client.lists.delete(list_id='0014d562f6')
        raise Warning(_("Connection Successfull"))

    #To remove member from list of mailchimp
    @api.multi
    def remove_member(self,list,email):
        client = self.mailchimp_connect()
        del_memb = client.lists.members.delete(list_id=list, subscriber_hash=email)
        return True

    #To connect with Mailchimp
    @api.multi
    def mailchimp_connect(self):
        mailchimp = self.search([],limit=1)
        if mailchimp.api_email and mailchimp.api_key:
            try:
                client = MailChimp(mailchimp.api_key.strip(),mailchimp.api_email.strip())
                return client
            except Exception as e:
                raise ValidationError(_("Error Occured While Connection: %s")%e)
        else:
            raise UserError(_("Enter Mailchimp key and Mailchinp Email"))

    # To create members in the List(Audience)
    @api.multi
    def createlist_members(self,list_id,name,email):
        client = self.mailchimp_connect()
        mc_name = name.split(' ')
        member = client.lists.members.create(list_id,{
            "email_address":email,
            "status":"subscribed",
            "merge_fields":{
                "FNAME":mc_name[0],
                "LNAME":mc_name[1]}
        })
        return member

    #To update members in List(Audience)
    @api.multi
    def updatelist_members(self,list_id,contact):
        client = self.mailchimp_connect()
        name = contact.name.split(' ')
        data = {
            "email_address":contact.email,
            "status":"subscribed",
            "merge_fields":{
                "FNAME":name[0],
                "LNAME":name[1]}
        }
        member = client.lists.members.update(list_id,subscriber_hash=contact.email,data=data)
        return member

    # To create List(Audience)
    @api.multi
    def create_list(self,dict):
        client = self.mailchimp_connect()
        data = {'name':dict["name"],
                'contact':{"company": dict["company"],
                            "address1": dict["address1"],
                            "address2": dict["address2"] if dict["address2"] else "Address 2",
                            "city": dict["city"],
                            "state": dict["state"],
                            "zip": dict["zip"],
                            "country": dict["country"],
                            "phone": dict["phone"]},
                'permission_reminder':'ok',
                'campaign_defaults':{'from_name':dict["from_name"],
                                     'from_email':dict["email"],
                                     'subject':dict["name"],
                                     'language':'English'},
                'email_type_option':False,
                }
        list = client.lists.create(data)
        return list

    #To get all templates
    @api.multi
    def get_all_templates(self):
        client = self.mailchimp_connect()
        templates = client.templates.all(get_all=False)
        mc_template_obj = self.env['mailchimp.template']
        if templates:
            for each_temp in templates["templates"]:
                mc_template = mc_template_obj.search([('mc_template_id','=',each_temp["id"])])
                if not mc_template and each_temp["type"]!='base':
                    template = mc_template_obj.create({'name':each_temp["name"],
                                                       'mc_template_id':each_temp["id"],})

    # To get List
    @api.multi
    def get_list(self,list):
        client = self.mailchimp_connect()
        list_id = client.lists.get(list_id=list)
        return list_id

    # To get all lists
    @api.multi
    def get_all_lists(self):
        client = self.mailchimp_connect()
        a_list = []
        list_obj = self.env['mailchimp.lists']
        try:
            lists = client.lists.all(get_all=False)
            if lists:
                for list in lists["lists"]:
                    a_list.append(list["id"])
                    mc_list = list_obj.search([('mailchimp_list_id','=',list["id"])])
                    if not mc_list:
                        audience = list_obj.create({'mailchimp_list_id':list["id"]})
                        audience.get_members()
                        self._cr.commit()
                    else:
                        mc_list.get_members()
                        self._cr.commit()
                for lines in list_obj.search([]):
                    if lines.mailchimp_list_id not in a_list:
                        self._cr.execute("delete from mailchimp_lists_rel where mailchimp_list_id=%s"%(lines.id))
                        lines.unlink()
        except Exception as e:
            raise ValidationError(_("Something Went Wrong : %s") % e)

    # To get all members from list
    @api.multi
    def get_members_all(self,list_id):
        client = self.mailchimp_connect()
        members = client.lists.members.all(list_id=list_id,get_all=False)
        return members

    # Create a campaign in Mailchimp
    @api.multi
    def create_campaign(self,record,data,name,email,audience,mc_template):
        client = self.mailchimp_connect()
        campaign_data = {"settings": {"title":record.name,
                                      "subject_line": record.subject,
                                      "from_name": name,
                                      "reply_to":email,
                                      "use_conversation":True},
                         "recipients": {"list_id":audience},
                         "type": "regular"}
        if mc_template:
            campaign_data.update({"template_id":mc_template,})
        campaign = client.campaigns.create(campaign_data)
        if not mc_template:
            campaign_id = campaign["id"]
            campaign = client.campaigns.content.update(campaign_id=campaign_id, data=data)
        return campaign


