from django.views import View
from meiduo_mall.libs.captcha.captcha import captcha
from django_redis import get_redis_connection
from django import http
from meiduo_mall.utils.response_code import RETCODE
from random import randint
from celery_tasks.sms.tasks import send_sms_code
from . import constants
# Create your views here.
import logging
logger = logging.getLogger('django')
class ImageCodeView(View):
    def get(self,request,uuid):
        name,text,image = captcha.generate_captcha()
        redis_conn = get_redis_connection('verify_code')
        redis_conn.setex('img_%s'%uuid,constants.IMAGE_CODE_REDIS_EXPIRES,text)
        return http.HttpResponse(image,content_type='image/jpg')


class SMSCodeView(View):
    def get(self,request,mobile):
        # 创建redis连接对象
        redis_conn = get_redis_connection('verify_code')
        send_flag = redis_conn.get('send_flag_%s'%mobile)
        #接受前端传过来的参数
        image_code_client = request.GET.get('image_code')
        uuid = request.GET.get('uuid')
        #判断参数是否齐全
        if not all([image_code_client,uuid]):
            return http.JsonResponse({'code':RETCODE.NECESSARYPARAMERR,'errmsg':'缺少必传参数'})


        #判断图形验证玛是否一致
        image_code_server = redis_conn.get('img_%s'%uuid)
        if image_code_server is None or image_code_client.lower() !=image_code_server.decode().lower():
            return http.JsonResponse({'code':RETCODE.IMAGECODEERR,'errmsg':'图形验证码错误'})

        #发送短信
        sms_code = '%06d'%randint(0,constants.AUTH_CODE)
        logger.info(sms_code)
        pl = redis_conn.pipeline()
        pl.setex('sms_%s'%mobile,constants.SMS_CODE_REDIS_EXPIRES,sms_code)
        pl.setex('send_flag_%s'%mobile,60,1)
        pl.execute()
        # CCP().send_template_sms(mobile,[sms_code,5],constants.SEND_SMS_TEMPLATE_ID)
        send_sms_code.delay(mobile,sms_code)
        return http.JsonResponse({'code':RETCODE.OK,'errmsg':'发送短信验证码'})