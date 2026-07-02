from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # ---------- Product & Cart ---------- #
    path("",                            views.product_list,      name="product_list"),
    path("cart/",                       views.cart,              name="cart"),
    path("add/<int:product_id>/",       views.add_to_cart,       name="add_to_cart"),
    path("remove/<int:item_id>/",       views.remove_from_cart,  name="remove_from_cart"),
    path("decrease/<int:item_id>/",     views.decrease_quantity, name="decrease_quantity"),
    path("checkout/",                   views.checkout,          name="checkout"),
    path("checkout/success/<int:order_id>/", views.checkout_success, name="checkout_success"),  # ✅ added

    # ---------- Customer Auth ---------- #
    path("login/",                      views.customer_login_view, name="login"),
    path("register/",                   views.register_view,       name="register"),
    path("logout/",                     views.logout_view,         name="logout"),

    # ---------- Admin Auth ---------- #
    path("admin/login/",                views.admin_login_view,    name="admin_login"),
    path("admin/dashboard/",            views.admin_dashboard,     name="admin_dashboard"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="store/login_customer.html"), name="default_login"),
    path('product/<int:product_id>/', views.product_detail,name='product_detail'),
]
