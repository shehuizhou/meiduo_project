from django.conf.urls import url
# from django.contrib.auth.decorators import login_required
from . import views

urlpatterns = [
    #注册
    url(r'^register/$',views.RegisterView.as_view(),name='register'),
    #判断用户是否已注册
    url(r'^usernames/(?P<username>[a-zA-Z0-9_-]{5,20})/count/$',views.UsernameCountView.as_view()),
    #判断手机号是否注册
    url(r'^mobiles/(?P<mobile>1[345789]\d{9})/count/$',views.MobileCountView.as_view()),
    #用户登陆
    url(r'^login/$',views.LoginView.as_view(),name='login'),
    #退出登陆
    url(r'^logout/$',views.LogoutView.as_view()),
    #用户中心
    url(r'^info/$',views.UserInfoView.as_view(),name='info'),
    #设置用户邮箱
    url(r'^emails/$',views.EmailView.as_view()),
    #激活邮箱
    url(r'^emails/verification/$',views.VerifyEmailView.as_view()),
    #用户地址
    url(r'^addresses/$',views.AddressView.as_view()),
    #用户新增地址
    url(r'^addresses/create/$',views.CreateAddressView.as_view()),
    #用户修改地址
    url(r'^addresses/(?P<address_id>\d+)/$',views.UpdateDestroyAddressView.as_view()),
    #用户默认地址
    url(r'^addresses/(?P<address_id>\d+)/default/$',views.DefaultAddressView.as_view()),
    #用户地址标题
    url(r'^addresses/(?P<address_id>\d+)/title/$',views.UpdateTitleAddressView.as_view()),
    #用户修改密码
    url(r'^password/$',views.ChangePasswordView.as_view()),
    url(r'^browse_histories/$', views.UserBrowseHistory.as_view()),

]