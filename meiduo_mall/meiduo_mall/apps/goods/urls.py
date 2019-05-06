from django.conf.urls import url
from . import views
urlpatterns = [
    url(r'^list/(?P<category_id>\d+)/(?P<page_num>\d+)/$',views.ListView.as_view(),name='index'),
    url(r'^hot/(?P<category_id>\d+)/$',views.HotGoodsView.as_view()),
    url(r'^detail/(?P<sku_id>\d+)/$',views.DetailView.as_view()),
]