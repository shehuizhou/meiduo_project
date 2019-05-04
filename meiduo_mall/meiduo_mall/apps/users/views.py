from django.shortcuts import render,redirect,reverse
from django.contrib.auth.models import AbstractUser
from django.views import View
from django import http
from .utils import generate_verify_email_url,check_token_to_user
import json
import re
from django.contrib.auth import login,authenticate,logout,mixins
from django.db import DatabaseError
from django_redis import get_redis_connection
from .models import User
import logging
from django.conf import settings
from meiduo_mall.utils.response_code import RETCODE
from celery_tasks.email.tasks import send_verify_email
logger = logging.getLogger('django')
# Create your views here.
class RegisterView(View):
    def get(self,request):
        return render(request,'register.html')

    def post(self,request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        mobile = request.POST.get('mobile')
        sms_code = request.POST.get('sms_code')
        allow = request.POST.get('allow')

        if all([username,password,password2,mobile,sms_code,allow]) is False:
            return http.HttpResponseForbidden('缺少参数')

        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$',username):
            return http.HttpResponseForbidden('请输入正确的用户名')
        if not re.match(r'^[0-9A-Za-z]{8,20}$',password):
            return http.HttpResponseForbidden('请输入正确的密码')
        if password !=password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')
        if not re.match(r'^1[345789]\d{9}$',mobile):
            return http.HttpResponseForbidden('请输入正确的手机号')
        #TODO
        redis_coon = get_redis_connection('verify_code')
        sms_code_server = redis_coon.get('sms_%s'%mobile)
        if sms_code_server is None or sms_code != sms_code_server.decode():
            return http.HttpResponseForbidden('短信验证码有误')
        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                mobile=mobile
            )
        except DatabaseError as e:
            logger.error(e)
            return render(request,'register.html',{'register_errmsg':'用户注册失败'})
        login(request,user)#状态保持
        response = redirect('/')
        response.set_cookie('username', user.username, max_age=settings.SESSION_COOKIE_AGE)
        return response


class UsernameCountView(View):
    def get(self,reuqest,username):
        count = User.objects.filter(username=username).count()
        return http.JsonResponse({'count':count,'code':RETCODE.OK,'errmsg':'OK'})


class MobileCountView(View):
    def get(self,reuqest,mobile):
        count = User.objects.filter(mobile=mobile).count()
        return http.JsonResponse({'count':count,'code':RETCODE.OK,'errmsg':'OK'})


class LoginView(View):
    def get(self,request):
        return render(request,'login.html')
    def post(self,request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        remembered = request.POST.get('remembered')

        if all([username,password]) is False:
            return http.HttpResponseForbidden('缺少必传参数')
        # user = User.objects.get(username=username)
        user = authenticate(username=username,password=password)
        if user is None:
            return render(request,'login.html',{'account_errmsg':'用户或密码错误'})
        # if remembered !='on':
        #     settings.SESSION_COOKIE_AGE= 0
        # login(request,user)
        login(request, user)
        if remembered != 'on':
            request.session.set_expiry(0)
        response =  redirect(request.GET.get('next','/'))
        response.set_cookie('username',user.username,max_age=settings.SESSION_COOKIE_AGE)
        return response


class LogoutView(View):
    def get(self,request):
        logout(request)
        response = redirect(reverse('users:login'))
        response.delete_cookie('username')
        return response


class UserInfoView(mixins.LoginRequiredMixin,View):
    def get(self,request):
        user = request.user
        # if user.is_authenticated:
        #     return render(request,'user_center_info.html')
        # else:
        #     return redirect('/login/?next=/info/')
        return render(request, 'user_center_info.html')


class EmailView(mixins.LoginRequiredMixin,View):
    def put(self,request):
        json_dict = json.loads(request.body.decode())
        email = json_dict.get('email')
        if all([email]) is None:
            return http.HttpResponseForbidden('缺少邮箱数据')
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',email):
            return http.HttpResponseForbidden('邮箱格式错误')
        user = request.user
        user.email = email
        user.save()
        # from django.core.mail import send_mail
        # send_mail('美多','','美多商城<18674447448@163.com>',[email],html_message='收钱吧到帐：1亿元')
        # verify_url = 'http://www.meiduo.site:8000/emails/verification/?token=2'
        verify_url = generate_verify_email_url(user)
        send_verify_email.delay(email,verify_url)

        return http.JsonResponse({'code':RETCODE.OK,'errmsg':'OK'})


class VerifyEmailView(View):
    def get(self,request):
        token = request.GET.get('token')
        user = check_token_to_user(token)
        if user is None:
            return http.HttpResponseForbidden('token无效')
        user.email_active = True
        user.save()
        return redirect('/info/')


class AddressView(mixins.LoginRequiredMixin,View):
    def get(self,request):
        return render(request,'user_center_site.html')