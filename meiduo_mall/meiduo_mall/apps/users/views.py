from django.shortcuts import render,redirect,reverse
from django.contrib.auth.models import AbstractUser
from django.views import View
from django import http
from .utils import generate_verify_email_url,check_token_to_user
import json
import re
from goods.models import SKU
from django.contrib.auth import login,authenticate,logout,mixins
from django.db import DatabaseError
from django_redis import get_redis_connection
from .models import User,Address
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
    def get(self, request):
        """提供收货地址界面"""
        # 获取用户地址列表
        login_user = request.user
        addresses = Address.objects.filter(user=login_user, is_deleted=False)

        address_dict_list = []
        for address in addresses:
            address_dict = {
                "id": address.id,
                "title": address.title,
                "receiver": address.receiver,
                "province": address.province.name,
                "city": address.city.name,
                "district": address.district.name,
                "place": address.place,
                "mobile": address.mobile,
                "tel": address.tel,
                "email": address.email
            }
            address_dict_list.append(address_dict)


        context = {
            'default_address_id': login_user.default_address_id,
            'addresses': address_dict_list,
        }

        return render(request, 'user_center_site.html', context)


class CreateAddressView(mixins.LoginRequiredMixin, View):
    """新增地址"""

    def post(self, request):
        """实现新增地址逻辑"""
        # 判断是否超过地址上限：最多20个
        # Address.objects.filter(user=request.user).count()
        count = request.user.addresses.count()
        if count >= 20:
            return http.JsonResponse({'code': RETCODE.THROTTLINGERR, 'errmsg': '超过地址数量上限'})

        # 接收参数
        json_dict = json.loads(request.body.decode())
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')

        # 校验参数
        if not all([receiver, province_id, city_id, district_id, place, mobile]):
            return http.HttpResponseForbidden('缺少必传参数')
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('参数mobile有误')
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('参数tel有误')
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('参数email有误')

        # 保存地址信息
        try:
            address = Address.objects.create(
                user=request.user,
                title = receiver,
                receiver = receiver,
                province_id = province_id,
                city_id = city_id,
                district_id = district_id,
                place = place,
                mobile = mobile,
                tel = tel,
                email = email
            )

            # 设置默认地址
            if not request.user.default_address:
                request.user.default_address = address
                request.user.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '新增地址失败'})

        # 新增地址成功，将新增的地址响应给前端实现局部刷新
        address_dict = {
            "id": address.id,
            "title": address.title,
            "receiver": address.receiver,
            "province": address.province.name,
            "city": address.city.name,
            "district": address.district.name,
            "place": address.place,
            "mobile": address.mobile,
            "tel": address.tel,
            "email": address.email
        }

        # 响应保存结果
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '新增地址成功', 'address':address_dict})


class UpdateDestroyAddressView(mixins.LoginRequiredMixin, View):
    """修改和删除地址"""

    def put(self, request, address_id):
        """修改地址"""
        # 接收参数
        json_dict = json.loads(request.body.decode())
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')

        # 校验参数
        if not all([receiver, province_id, city_id, district_id, place, mobile]):
            return http.HttpResponseForbidden('缺少必传参数')
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('参数mobile有误')
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('参数tel有误')
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('参数email有误')

        # 判断地址是否存在,并更新地址信息
        try:
            Address.objects.filter(id=address_id).update(
                user = request.user,
                title = receiver,
                receiver = receiver,
                province_id = province_id,
                city_id = city_id,
                district_id = district_id,
                place = place,
                mobile = mobile,
                tel = tel,
                email = email
            )
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '更新地址失败'})

        # 构造响应数据
        address = Address.objects.get(id=address_id)
        address_dict = {
            "id": address.id,
            "title": address.title,
            "receiver": address.receiver,
            "province": address.province.name,
            "city": address.city.name,
            "district": address.district.name,
            "place": address.place,
            "mobile": address.mobile,
            "tel": address.tel,
            "email": address.email
        }

        # 响应更新地址结果
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '更新地址成功', 'address': address_dict})

    def delete(self, request, address_id):
        """删除地址"""
        try:
            # 查询要删除的地址
            address = Address.objects.get(id=address_id)

            # 将地址逻辑删除设置为True
            address.is_deleted = True
            address.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '删除地址失败'})

        # 响应删除地址结果
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '删除地址成功'})


class DefaultAddressView(mixins.LoginRequiredMixin, View):
    """设置默认地址"""

    def put(self, request, address_id):
        """设置默认地址"""
        try:
            # 接收参数,查询地址
            address = Address.objects.get(id=address_id)

            # 设置地址为默认地址
            request.user.default_address = address
            request.user.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '设置默认地址失败'})

        # 响应设置默认地址结果
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '设置默认地址成功'})


class UpdateTitleAddressView(mixins.LoginRequiredMixin, View):
    """设置地址标题"""

    def put(self, request, address_id):
        """设置地址标题"""
        # 接收参数：地址标题
        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')

        try:
            # 查询地址
            address = Address.objects.get(id=address_id)

            # 设置新的地址标题
            address.title = title
            address.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '设置地址标题失败'})

        # 4.响应删除地址结果
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '设置地址标题成功'})


class ChangePasswordView(mixins.LoginRequiredMixin, View):
    """修改密码"""

    def get(self, request):
        """展示修改密码界面"""
        return render(request, 'user_center_pass.html')

    def post(self, request):
        """实现修改密码逻辑"""

        # 接收参数
        old_password = request.POST.get('old_pwd')
        new_password = request.POST.get('new_pwd')
        new_password2 = request.POST.get('new_cpwd')

        # 校验参数
        if not all([old_password, new_password, new_password2]):
            return http.HttpResponseForbidden('缺少必传参数')
        # 判断旧密码是否正确
        if request.user.check_password(old_password) is False:
            return render(request, 'user_center_pass.html', {'origin_pwd_errmsg':'原始密码错误'})
        if not re.match(r'^[0-9A-Za-z]{8,20}$', new_password):
            return http.HttpResponseForbidden('密码最少8位，最长20位')
        if new_password != new_password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        # 修改密码
        try:
            request.user.set_password(new_password)
            request.user.save()
        except Exception as e:
            logger.error(e)
            return render(request, 'user_center_pass.html', {'change_pwd_errmsg': '修改密码失败'})

        # 清理状态保持信息
        logout(request)
        response = redirect(reverse('users:login'))
        response.delete_cookie('username')

        # # 响应密码修改结果：重定向到登录界面
        return response


class UserBrowseHistory(View):
    """用户商品浏览记录"""

    def post(self, request):

        # 判断当前用户是否登录
        user = request.user
        if not user.is_authenticated:
            return http.JsonResponse({'code': RETCODE.SESSIONERR, 'errmsg': '用户未登录'})

        # 获取请求体中的sku_id
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')

        # 校验sku_id
        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return http.HttpResponseForbidden('sku_id不存在')

        # 创建redis连接对象
        redis_conn = get_redis_connection('history')
        pl = redis_conn.pipeline()

        key = 'history_%s' % user.id
        # 先去重
        pl.lrem(key, 0, sku_id)

        # 存储到列表的开头
        pl.lpush(key, sku_id)

        # 截取前5个
        pl.ltrim(key, 0, 4)
        # 执行管道
        pl.execute()

        # 响应
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})

    def get(self, request):
        """浏览记录查询"""

        # 创建redis连接对象
        redis_conn = get_redis_connection('history')
        sku_id_list = redis_conn.lrange('history_%s' % request.user.id, 0, -1)
        # 获取当前登录用户的浏览记录列表数据 [sku_id1, sku_id2]

        # 通过sku_id查询sku,再将sku模型转换成字典
        # sku_qs = SKU.objects.filter(id__in=sku_id_list)  [b'3', b'2', b'5'] [2, 3, 5]
        skus = []  # 用来装每一个sku字典
        for sku_id in sku_id_list:
            sku = SKU.objects.get(id=sku_id)
            sku_dict = {
                'id': sku.id,
                'name': sku.name,
                'default_image_url': sku.default_image.url,
                'price': sku.price
            }
            skus.append(sku_dict)
        # 响应
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'skus': skus})