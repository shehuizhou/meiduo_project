from django.shortcuts import render
from django.views import View
from django import http
from django.core.paginator import Paginator
from django.utils import timezone

from contents.utils import get_categories
from .models import GoodsCategory,SKU,GoodsVisitCount
from .utils import get_breadcrumb
from meiduo_mall.utils.response_code import RETCODE


class ListView(View):
    """商品列表界面"""

    def get(self, request, category_id, page_num):
        """
        :param category_id: 当前选择的三级类别id
        :param page_num: 第几页
        """
        try:
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return http.HttpResponseNotFound('商品类别不存在')

        # 获取查询参数中的sort 排序规则
        sort = request.GET.get('sort', 'default')

        if sort == 'price':
            sort_fields = 'price'
        elif sort == 'hot':
            sort_fields = '-sales'
        else:
            sort_fields = 'create_time'

        # 面包屑导航数据
        # a = (page_num - 1) * 5
        # b = a + 5
        # 查询当前三级类别下面的所有sku
        # order_by(只能放当前查询集中每个模型中的字段)
        sku_qs = category.sku_set.filter(is_launched=True).order_by(sort_fields)

        # 创建分页对象
        paginator = Paginator(sku_qs, 5)  # Paginator(要进行分页的所有数据, 每页显示多少条数据)
        page_skus = paginator.page(page_num)  # 获取指定界面的sku数据
        total_page = paginator.num_pages  # 获取当前的总页数

        context = {
            'categories': get_categories(),  # 频道分类
            'breadcrumb': get_breadcrumb(category),  # 面包屑导航
            'sort': sort,  # 排序字段
            'category': category,  # 第三级分类
            'page_skus': page_skus,  # 分页后数据
            'total_page': total_page,  # 总页数
            'page_num': page_num,  # 当前页码
        }

        return render(request, 'list.html', context)


class HotGoodsView(View):
    """热销排行数据"""

    def get(self, request, category_id):

        try:
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return http.HttpResponseNotFound('商品类别不存在')

        # 获取当前三级类别下面销量最高的前两个sku
        skus_qs = category.sku_set.filter(is_launched=True).order_by('-sales')[0:2]

        hot_skus = []  # 包装两个热销商品字典
        for sku in skus_qs:
            hot_skus.append({
                'id': sku.id,
                'name': sku.name,
                'price': sku.price,
                'default_image_url': sku.default_image.url
            })

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'hot_skus': hot_skus})


class DetailView(View):
    def get(self,request,sku_id):

        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return render(request,'404.html')
        category = sku.category
        spu = sku.spu
        context = {
            'categories':get_categories(),
            'breadcrumb':get_breadcrumb(category),
            'sku':sku,
            'category':category,
            'spu':spu,
        }
        return render(request,'detail.html',context)
        pass


class DetailVisitView(View):
    """商品类别每日访问量统计"""

    def post(self, request, category_id):

        try:
            # 校验category_id 是否真实存在
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return http.HttpResponseForbidden('商品类别不存在')

        # 获取当前日期
        today_date = timezone.localdate()
        try:

            # 查询当前类别今天没有没统计过  # 注意不要写成data了
            count_data = GoodsVisitCount.objects.get(category=category, date=today_date)
        except GoodsVisitCount.DoesNotExist:
            # 如果当前类别今天是第一次来统计,就创建一个新记录,并给它指定是统计那一个类别
            count_data = GoodsVisitCount(
                category=category

            )

        count_data.count += 1  # 累加浏览量
        count_data.save()


        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': "ok"})