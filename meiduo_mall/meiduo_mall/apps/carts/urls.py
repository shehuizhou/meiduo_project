from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^carts/$',views.CatsView.as_view()),
]