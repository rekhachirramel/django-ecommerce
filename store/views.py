import razorpay
from django.conf import settings
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q, Sum,Avg
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CheckoutForm
from .models import CartItem, Order, Product, Review
 
@login_required
def product_detail(request, product_id):

    product = get_object_or_404(Product, id=product_id)

    reviews = Review.objects.filter(product=product)

    average_rating = reviews.aggregate(
        Avg('rating')
    )['rating__avg']

    if request.method == "POST":

        rating = int(request.POST.get("rating"))
        comment = request.POST.get("comment")

        review, created = Review.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={
                "rating": rating,
                "comment": comment,
            }
        )

        if created:
            messages.success(
                request,
                "Review submitted successfully."
            )
        else:
            messages.success(
                request,
                "Review updated successfully."
            )

        return redirect(
            'product_detail',
            product_id=product.id
        )

    return render(
        request,
        'store/product_detail.html',
        {
            'product': product,
            'reviews': reviews,
            'average_rating': average_rating,
        }
    )
# ---------------------------------------------------------------------
# Helper: check if user is staff / superuser
# ---------------------------------------------------------------------
def is_admin(user):
    return user.is_authenticated and user.is_staff


# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------
def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        confirm = request.POST.get("confirm")

        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect("register")

        user = User.objects.create_user(username=username, password=password)
        login(request, user)  # Auto login
        return redirect("product_list")

    return render(request, "store/register.html")


# ---------------------------------------------------------------------
# Customer login (non-staff only)
# ---------------------------------------------------------------------
def customer_login_view(request):
    next_url = request.GET.get("next")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        if user and not user.is_staff:
            login(request, user)
            return redirect(next_url or "product_list")

        messages.error(request, "Invalid credentials or not a customer account.")
        return redirect("login")

    if next_url:
        messages.info(request, "Please log in to continue.")

    return render(request, "store/login_customer.html")


# ---------------------------------------------------------------------
# Admin login (staff only)
# ---------------------------------------------------------------------
def admin_login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        if user and user.is_staff:
            login(request, user)
            return redirect("admin_dashboard")

        messages.error(request, "Invalid credentials or not an admin account.")
        return redirect("admin_login")

    return render(request, "store/login_admin.html")


# ---------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------
def logout_view(request):
    logout(request)
    return redirect("product_list")


# ---------------------------------------------------------------------
# Product List (Search)
# ---------------------------------------------------------------------
def product_list(request):
    q = request.GET.get("q", "").strip()
    products = Product.objects.all()
    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    return render(request, "store/product_list.html", {"products": products, "query": q})


# ---------------------------------------------------------------------
# Cart Views
# ---------------------------------------------------------------------
@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    item, created = CartItem.objects.get_or_create(user=request.user, product=product)
    item.quantity = 1 if created else item.quantity + 1
    item.save()
    return redirect("cart")


@login_required
def decrease_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    if item.quantity > 1:
        item.quantity -= 1
        item.save()
    else:
        item.delete()
    return redirect("cart")


@login_required
def remove_from_cart(request, item_id):
    get_object_or_404(CartItem, id=item_id, user=request.user).delete()
    return redirect("cart")


@login_required
def cart(request):
    items = CartItem.objects.filter(user=request.user)
    total = (
        items.aggregate(
            total_price=Sum("product__price", field="product__price * quantity")
        )["total_price"]
        or Decimal("0.00")
    )
    return render(request, "store/cart.html", {"cart_items": items, "total": total})


# ---------------------------------------------------------------------
# Checkout with Razorpay
# ---------------------------------------------------------------------
@login_required
def checkout(request):
    items = CartItem.objects.filter(user=request.user)
    if not items.exists():
        messages.info(request, "Your cart is empty.")
        return redirect("cart")

    total = (
        items.aggregate(
            total_price=Sum("product__price", field="product__price * quantity")
        )["total_price"]
        or Decimal("0.00")
    )

    total_amount = int(total * 100)  # Razorpay expects amount in paisa

    # Razorpay client
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    # Create Razorpay order
    razorpay_order = client.order.create({
        "amount": total_amount,
        "currency": "INR",
        "payment_capture": "1",
    })

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user
            order.total = total
            order.save()

            items.delete()

            return redirect("checkout_success", order_id=order.id)

    else:
        form = CheckoutForm()

    return render(
        request,
        "store/checkout.html",
        {
            "form": form,
            "cart_items": items,
            "total": total,
            "razorpay_key": settings.RAZORPAY_KEY_ID,
            "razorpay_order_id": razorpay_order["id"],
            "razorpay_amount": total_amount,
        },
    )


# ---------------------------------------------------------------------
# Checkout Success
# ---------------------------------------------------------------------
@login_required
def checkout_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "store/checkout_success.html", {"order": order})


# ---------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------
@user_passes_test(is_admin)
def admin_dashboard(request):
    total_orders = Order.objects.count()
    total_sales = Order.objects.aggregate(Sum("total"))["total__sum"] or Decimal("0.00")
    return render(
        request,
        "store/admin_dashboard.html",
        {"total_orders": total_orders, "total_sales": total_sales},
    )
