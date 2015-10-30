# -*- coding: utf8 -*-
#from django.views.decorators.cache import never_cache
from django.template.response import TemplateResponse
from django.http.response import HttpResponse

from www.views import AuthedView, LeftSideBarMixin
from www.decorator import perm_required
from www.models import Users, PermRelTenant, AppServiceInfo, ServiceInfo, TenantServiceRelation
from www.forms.services import ServicePublishForm
from www.utils import increase_version

import logging
logger = logging.getLogger('default')


class TeamInfo(LeftSideBarMixin, AuthedView):

    def get_context(self):
        context = super(TeamInfo, self).get_context()
        context.update({
            'perm_users': self.get_user_perms(),
            'tenantName': self.tenantName,
        })
        context["teamStatus"] = "active"
        return context

    def get_media(self):
        media = super(TeamInfo, self).get_media() + self.vendor(
            'www/css/goodrainstyle.css', 'www/js/jquery.cookie.js', 'www/js/service.js',
            'www/js/gr/basic.js', 'www/css/gr/basic.css', 'www/js/perms.js', 'www/js/common-scripts.js', 'www/js/jquery.dcjqaccordion.2.7.js', 'www/js/jquery.scrollTo.min.js'
        )
        return media

    def get_response(self):
        return TemplateResponse(self.request, 'www/team.html', self.get_context())

    def get_user_perms(self):
        perm_users = []
        perm_template = {
            'name': None,
            'adminCheck': False,
            'developerCheck': False, 'developerDisable': False,
            'viewerCheck': False, 'viewerDisable': False
        }

        identities = PermRelTenant.objects.filter(tenant_id=self.tenant.pk)
        for i in identities:
            user_perm = perm_template.copy()
            user_perm['name'] = Users.objects.get(pk=i.user_id).nick_name
            if i.identity == 'admin':
                user_perm.update({
                    'adminCheck': True,
                    'developerCheck': True, 'developerDisable': True,
                    'viewerCheck': True, 'viewerDisable': True
                })
            elif i.identity == 'developer':
                user_perm.update({
                    'developerCheck': True,
                    'viewerCheck': True, 'viewerDisable': True
                })
            elif i.identity == 'viewer':
                user_perm.update({
                    'viewerCheck': True
                })

            perm_users.append(user_perm)

        return perm_users

    @perm_required('tenant_access')
    def get(self, request, *args, **kwargs):
        return self.get_response()


class ServicePublishView(AuthedView):

    def get_context(self):
        context = super(ServicePublishView, self).get_context()
        context.update({
            'form': self.form,
        })
        return context

    def get_media(self):
        media = super(ServicePublishView, self).get_media(
        ) + self.vendor('www/css/goodrainstyle.css', 'www/js/jquery.cookie.js', 'www/js/validator.min.js')
        return media

    def get_response(self):
        return TemplateResponse(self.request, 'www/service/publish.html', self.get_context())

    def prepare_app_update(self, last_pub_version):
        app = ServiceInfo.objects.get(service_key=last_pub_version.service_key)
        form_init_data = {
            'app_key': {"value": app.service_key, "attrs": {"readonly": True}},
            'app_name': {"value": app.service_name, "attrs": {"readonly": True}},
            'app_version': {"value": increase_version(last_pub_version.app_version, 1)},
            'app_info': {"value": app.info},
            'pay_type': {"value": last_pub_version.pay_type},
            'price': {"value": last_pub_version.price},
        }
        return form_init_data

    def get(self, request, *args, **kwargs):
        published_versions = AppServiceInfo.objects.filter(service_id=self.service.service_id).order_by('-create_time')
        if published_versions:
            last_pub_version = published_versions[0]
            form_init_data = self.prepare_app_update(last_pub_version)
            self.form = ServicePublishForm(initial=form_init_data, is_update=True)
        else:
            self.form = ServicePublishForm()
        return self.get_response()

    def post(self, request, *args, **kwargs):
        self.form = ServicePublishForm(request.POST)
        if not self.form.is_valid():
            return self.get_response()

        post_data = request.POST.dict()
        logger.debug("service.publish", "post_data is {0}".format(post_data))
        if 'publish' in post_data:
            action = 'app_publish'
        elif 'update' in post_data:
            action = 'app_update'
        else:
            return HttpResponse("error", status=500)

        func = getattr(self, action)
        try:
            success = func(post_data)
            if success:
                return self.redirect_to('/apps/{0}/service/'.format(self.tenantName))
            else:
                logger.error('service.publish', "{} failed".format(action))
                return HttpResponse(u"发布过程出现异常", status=500)
        except Exception, e:
            logger.exception('service.publish', e)
            return HttpResponse(u"应用发布失败", status=500)

    def app_publish(self, post_data):
        try:
            app = self._add_new_app(post_data, self.service)
            self.create_new_version(app, post_data, self.service)
            app.save()
            return True
        except Exception, e:
            logger.exception('service.publish', e)
            return False

    def app_update(self, post_data):
        try:
            app = self._update_app(post_data, self.service)
            self.create_new_version(app, post_data, self.service)
            app.save()
            return True
        except Exception, e:
            logger.exception('service.publish', e)
            return False

    def _add_new_app(self, d, pub_service):
        try:
            app = ServiceInfo(service_key=d['app_key'], publisher=self.user.nick_name, service_name=d['app_name'], info=d['app_info'],
                              status="test", category="app_publish", version=d['app_version'])
            app = self.copy_public_properties(pub_service, app)
            app.dependecy = self.get_pub_srv_deps(pub_service)
            return app
        except Exception, e:
            raise e

    def _update_app(self, d, pub_service):
        app = ServiceInfo.objects.get(service_key=d['app_key'])
        app.info = d['app_info']
        app.version = d['app_version']
        app.service_name = d['app_name']
        app.dependecy = self.get_pub_srv_deps(pub_service)
        return app

    def create_new_version(self, app, d, pub_service):
        new_version = AppServiceInfo(service_key=app.service_key, service_id=pub_service.service_id, pay_type=d['pay_type'], price=d['price'],
                                     deploy_version=pub_service.deploy_version, app_version=d['app_version'], change_log=d['change_log'])
        new_version = self.copy_public_properties(pub_service, new_version)
        new_env = self.extend_env(new_version, pub_service)
        new_version.env = new_env
        new_version.save()
        app.env = new_env

    def copy_public_properties(self, copy_from, to):
        for field in ('is_service', 'is_web_service', 'image', 'extend_method', 'cmd', 'setting', 'env',
                      'min_node', 'min_cpu', 'min_memory', 'inner_port', 'volume_mount_path', 'service_type'):
            if hasattr(to, field) and hasattr(copy_from, field):
                setattr(to, field, getattr(copy_from, field))
        return to

    def extend_env(self, app_version, pub_service):
        if pub_service.image.startswith('goodrain.me/runner'):
            SLUG_PATH = '/{0}/slug/{1}/{2}.tgz'.format(pub_service.tenant_id, pub_service.service_id, pub_service.deploy_version)
            return app_version.env.rstrip(',') + ',SLUG_PATH=' + SLUG_PATH + ','
        else:
            return app_version.env

    def get_pub_srv_deps(self, pub_service):
        deps = TenantServiceRelation.objects.filter(service_id=pub_service.service_id)
        if deps:
            dep_service_keys = list(set([e.dep_service_type for e in deps]))
            return ','.join(dep_service_keys)
        else:
            return ""
