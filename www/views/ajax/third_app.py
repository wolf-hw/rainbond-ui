# -*- coding: utf8 -*-
from django.http import JsonResponse
import json
from www.views import AuthedView
from www.models import ThirdAppInfo, CDNTrafficRecord, Tenants, CDNTrafficHourRecord, ThirdAppOperator
from www.third_app.cdn.upai.client import YouPaiApi
import logging
from www.utils.crypt import make_uuid
import datetime
from django.db import transaction

logger = logging.getLogger('default')


class UpdateAppView(AuthedView):
    def __init__(self, request, *args, **kwargs):
        
        self.app_id = kwargs.get('app_id', None)
        self.app_info = ThirdAppInfo.objects.get(bucket_name=self.app_id)
        AuthedView.__init__(self, request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """
        修改应用名
        """
        result = {}
        try:
            name = request.POST.get("name", "")
            if name == "":
                result["status"] = "failure"
                result["message"] = "应用名不能为空"
            else:
                self.app_info.name = name
                self.app_info.save()
                result["status"] = "success"
                result["message"] = "修改成功"
        except Exception, e:
            logger.exception(e)
            result["status"] = "failure"
            result["message"] = "修改失败"
        return JsonResponse(result)


class AppDomainView(AuthedView):
    def __init__(self, request, *args, **kwargs):
        
        self.app_id = kwargs.get('app_id', None)
        self.app_info = ThirdAppInfo.objects.get(bucket_name=self.app_id)
        AuthedView.__init__(self, request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        result = {}
        try:
            domain = request.POST.get("domain", "")
            if domain == "":
                result["status"] = "failure"
                result["message"] = "域名不能为空"
            else:
                body = {}
                body["domain"] = domain
                body["bucket_name"] = self.app_id
                upai_client = YouPaiApi()
                res, rebody = upai_client.addDomain(json.dumps(body))
                if res.status == 200:
                    result["status"] = "success"
                    result["message"] = "添加成功"
                else:
                    if type(rebody) is str:
                        rebody = json.loads(rebody)
                    result["status"] = "failure"
                    result["message"] = rebody.message
        except Exception, e:
            logger.exception(e)
            result["status"] = "failure"
            result["message"] = "添加失败"
        return JsonResponse(result)


class AppDomainDeleteView(AuthedView):
    def __init__(self, request, *args, **kwargs):
        self.app_id = kwargs.get('app_id', None)
        self.app_info = ThirdAppInfo.objects.get(bucket_name=self.app_id)
        AuthedView.__init__(self, request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        result = {}
        try:
            domain = request.POST.get("domain", "")
            if domain == "":
                result["status"] = "failure"
                result["message"] = "域名不能为空"
            else:
                upai_client = YouPaiApi()
                res, rebody = upai_client.deleteDomain(domain=domain, bucket=self.app_id)
                if res.status == 200:
                    result["status"] = "success"
                    result["message"] = "删除成功"
                else:
                    if type(rebody) is str:
                        rebody = json.loads(rebody)
                    result["status"] = "failure"
                    result["message"] = rebody.message
        except Exception, e:
            logger.exception(e)
            result["status"] = "failure"
            result["message"] = "删除失败"
        return JsonResponse(result)


class AppOperatorView(AuthedView):
    def __init__(self, request, *args, **kwargs):
        self.app_id = kwargs.get('app_id', None)
        self.app_info = ThirdAppInfo.objects.get(bucket_name=self.app_id)
        AuthedView.__init__(self, request, *args, **kwargs)
    
    def is_number(self, s):
        try:
            float(s)
            return True
        except ValueError:
            pass
        
        try:
            import unicodedata
            unicodedata.numeric(s)
            return True
        except (TypeError, ValueError):
            pass
        
        return False
    
    def post(self, request, *args, **kwargs):
        """
        添加操作员并授权。
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        result = {}
        try:
            upai_client = YouPaiApi()
            operator_name = request.POST.get("operator_name", "")
            password = request.POST.get("password", "")
            realname = request.POST.get("realname", "")
            if operator_name == "":
                result["status"] = "failure"
                result["message"] = "用户名不能为空"
                return JsonResponse(result)
            if len(password) < 9 or self.is_number(password):
                result["status"] = "failure"
                result["message"] = "密码8位以上且不能都为数字"
                return JsonResponse(result)
            if realname == "":
                result["status"] = "failure"
                result["message"] = "姓名不能为空"
                return JsonResponse(result)
            else:
                body = {}
                body["operator_name"] = operator_name
                body["password"] = password
                body["realname"] = realname
                res, rebody = upai_client.addOperator(json.dumps(body))
                if res.status == 201:
                    res, rebody = upai_client.enableOperator(operator_name)
                    if res.status == 200:
                        authBody = {}
                        authBody["bucket_name"] = self.app_id
                        authBody["operator_name"] = operator_name
                        res, rebody = upai_client.addOperatorAuth(json.dumps(authBody))
                        if res.status == 201:
                            result["status"] = "success"
                            result["message"] = "添加成功"
                            count = ThirdAppOperator.objects.filter(operator_name=operator_name).count()
                            if count < 1:
                                operator = ThirdAppOperator(service_id=self.app_info.service_id,
                                                            bucket_name=self.app_id,
                                                            operator_name=operator_name, real_name=realname,
                                                            password=password)
                                operator.save()
                        else:
                            if type(rebody) is str:
                                rebody = json.loads(rebody)
                            result["status"] = "failure"
                            result["message"] = rebody.message
                    else:
                        if type(rebody) is str:
                            rebody = json.loads(rebody)
                        result["status"] = "failure"
                        result["message"] = rebody.message
                else:
                    if type(rebody) is str:
                        rebody = json.loads(rebody)
                    result["status"] = "failure"
                    result["message"] = rebody.message
        except Exception, e:
            logger.exception(e)
            result["status"] = "failure"
            result["message"] = "添加失败"
        return JsonResponse(result)


class AppOperatorDeleteView(AuthedView):
    def __init__(self, request, *args, **kwargs):
        self.app_id = kwargs.get('app_id', None)
        self.app_info = ThirdAppInfo.objects.get(bucket_name=self.app_id)
        AuthedView.__init__(self, request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        result = {}
        try:
            upai_client = YouPaiApi()
            operator_name = request.POST.get("operator_name", "")
            if operator_name == "":
                result["status"] = "failure"
                result["message"] = "操作员用户名不能为空"
            res, rebody = upai_client.deleteOperatorAuth(self.app_id, operator_name)
            if res.status == 200:
                upai_client.deleteOperator(operator_name)
                ThirdAppOperator.objects.filter(operator_name=operator_name).delete()
                result["status"] = "success"
                result["message"] = "删除成功"
            else:
                if type(rebody) is str:
                    rebody = json.loads(rebody)
                result["status"] = "failure"
                result["message"] = rebody.message
        except Exception, e:
            logger.exception(e)
            result["status"] = "failure"
            result["message"] = "删除失败"
        return JsonResponse(result)


class CDNTrafficRecordView(AuthedView):
    def __init__(self, request, *args, **kwargs):
        self.app_id = kwargs.get('app_id', None)
        self.app_info = ThirdAppInfo.objects.get(bucket_name=self.app_id)
        self.price_map = {
            "500G": 130,
            "1T": 260,
            "5T": 1250,
            "10T": 2440,
            "50T": 11200,
            "200T": 43000,
            "1PB": 204800,
        }
        self.size_map = {
            "500G": 1024 * 500 * 1024 * 1024,
            "1T": 1024 * 1024 * 1024 * 1024,
            "5T": 1024 * 1024 * 5 * 1024 * 1024,
            "10T": 1024 * 1024 * 10 * 1024 * 1024,
            "50T": 1024 * 1024 * 50 * 1024 * 1024,
            "200T": 1024 * 1024 * 200 * 1024 * 1024,
            "1PB": 1024 * 1024 * 1024 * 1024 * 1024,
        }
        AuthedView.__init__(self, request, *args, **kwargs)
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        result = {}
        try:
            traffic_size = request.POST.get("traffic_size", "500G")
            new_tenant = Tenants.objects.get(tenant_id=self.tenant.tenant_id)
            if new_tenant.balance < self.price_map[traffic_size] and new_tenant.pay_type != "unpay":
                result["status"] = "failure"
                result["message"] = "余额不足，请先充值！"
                return JsonResponse(result)
            
            # 创建订单
            record = CDNTrafficRecord()
            record.traffic_price = self.price_map[traffic_size]
            record.traffic_size = self.size_map[traffic_size]
            record.bucket_name = self.app_id
            record.service_id = self.app_info.service_id
            record.order_id = make_uuid()
            record.tenant_id = self.tenantName
            record.save()
            # 支付
            if new_tenant.pay_type != "unpay":
                new_tenant.balance = float(new_tenant.balance) - float(self.price_map[traffic_size])
                new_tenant.save()
            record.payment_status = 1
            record.save()
            
            # 创建流量包消费初始纪录或为历史纪录充值流量
            hour = CDNTrafficHourRecord.objects. \
                order_by("-end_time").filter(bucket_name=self.app_id, service_id=self.app_info.service_id).first()
            if hour is None:
                hour = CDNTrafficHourRecord()
                hour.balance = record.traffic_size
                hour.bucket_name = self.app_id
                hour.service_id = self.app_info.service_id
                hour.tenant_id = self.tenantName
                hour.traffic_number = 0
                hour.start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                hour.end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                hour.save()
            else:
                hour.balance = float(hour.balance) + float(record.traffic_size)
                hour.save()
            # 更新应用付费方式为包流量
            self.app_info.bill_type = "packet"
            self.app_info.save()
            result["status"] = "success"
            result["message"] = "购买成功"
            result["balance"] = hour.balance
        except Exception, e:
            transaction.rollback()
            logger.exception(e)
            result["status"] = "failure"
            result["message"] = "购买失败"
        return JsonResponse(result)


class OpenThirdAppView(AuthedView):
    def __init__(self, request, *args, **kwargs):
        self.app_id = kwargs.get('app_id', None)
        self.app_info = ThirdAppInfo.objects.get(bucket_name=self.app_id)
        AuthedView.__init__(self, request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """
        开启app
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        result = {}
        try:
            upai_client = YouPaiApi()
            if self.tenant.balance > 0:
                res, body = upai_client.openApp(self.app_id)
                if res.status == 200:
                    self.app_info.open = 1
                    self.app_info.save()
                else:
                    result["status"] = "failure"
                    result["message"] = body.message
            else:
                result["status"] = "failure"
                result["message"] = "余额不足"
        except Exception, e:
            logger.exception(e)
            result["status"] = "failure"
            result["message"] = "开启失败"
        return JsonResponse(result)


class DeleteThirdAppView(AuthedView):
    def __init__(self, request, *args, **kwargs):
        self.app_id = kwargs.get('app_id', None)
        self.app_info = ThirdAppInfo.objects.get(bucket_name=self.app_id)
        AuthedView.__init__(self, request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """
        删除第三方应用
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        result = {}
        try:
            if self.app_info.app_type == "upai_cdn" or self.app_info.app_type == "upai_oos":
                res = {}
                body = {}
                try:
                    upai_client = YouPaiApi()
                    res, body = upai_client.stopApp(self.app_id)
                except Exception, e:
                    result["status"] = "failure"
                    result["message"] = body.message
                if res.status == 200:
                    self.app_info.delete = 1
                    self.app_info.save()
                    result["status"] = "success"
                    result["message"] = "删除成功"
        except Exception, e:
            logger.exception(e)
            result["status"] = "failure"
            result["message"] = "删除失败"
        return JsonResponse(result)