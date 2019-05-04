from django.shortcuts import render,redirect
from django.views import View
from django import http
from .models import OAuthQQUser
from django.contrib.auth import login
import logging
from django.conf import settings
from meiduo_mall.utils.response_code import RETCODE
from .utils import generate_openid_signature,check_openid_sign
from QQLoginTool.QQtool import OAuthQQ
from users.models import User
import re
from django_redis import get_redis_connection
logger = logging.getLogger('django')
# Create your views here.
class OAuthURLView(View):
    def get(self,request):
        next = request.GET.get('next','/')
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI,
                        state=next)
        login_url = oauth.get_qq_url()
        return http.JsonResponse({'login_url':login_url,'code':RETCODE.OK,'errmsg':'OK'})


class OAuthUserView(View):
    def get(self,request):
        code = request.GET.get('code')
        state = request.GET.get('state','/')
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI,
                        )
        try:
            access_token = oauth.get_access_token(code)
            openid = oauth.get_open_id(access_token)
        except Exception as e:

            return http.JsonResponse({'code':RETCODE.SERVERERR,'errmsg':'QQ服务器宕机'})
        try:
            oauth_model =OAuthQQUser.objects.get(openid=openid)
        except OAuthQQUser.DoesNotExist:
            openid = generate_openid_signature(openid)
            return render(request,'oauth_callback.html', {'openid': openid})
        else:
            user = oauth_model.user
            login(request,user)
            response = redirect(state)
        # return http.JsonResponse({'openid':openid})
            response.set_cookie('username',user.username,max_age=settings.SESSION_COOKIE_AGE)
            return response

    def post(self,request):
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        sms_code = request.POST.get('sms_code')
        openid = request.POST.get('openid')

        if all([mobile,password,sms_code,openid]) is False:
            return http.HttpResponseForbidden('缺少必传参数')
        if not re.match(r'^1[345789]\d{9}$', mobile):
            return http.HttpResponseForbidden('请输入正确的手机号')

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.HttpResponseForbidden('请输入正确的密码')

        redis_coon = get_redis_connection('verify_code')
        sms_code_server = redis_coon.get('sms_%s' % mobile)
        if sms_code_server is None or sms_code != sms_code_server.decode():
            return http.HttpResponseForbidden('短信验证码有误')
        openid = check_openid_sign(openid)
        if openid is None:
            return http.HttpResponseForbidden('openid无效')
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=mobile,
                password=password,
                mobile=mobile,
            )
        else:
            if user.check_password(password) is False:
                return http.HttpResponseForbidden('账号或密码错误')

        OAuthQQUser.objects.create(
            user=user,
            openid=openid
        )
        login(request,user)
        response = redirect(request.GET.get('state'))
        response.set_cookie('username',user.username,max_age=settings.SESSION_COOKIE_AGE)
        return response