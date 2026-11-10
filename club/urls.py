from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Главная страница
    path('', views.home_view, name='home'),

    # Аутентификация
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='club/auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/club-card/', views.apply_club_card_view, name='apply_club_card'),

    # Каталог меню бара
    path('menu/', views.menu_catalog_view, name='menu_catalog'),

    # Бронирование (CRUD)
    path('bookings/', views.booking_list_view, name='booking_list'),
    path('bookings/create/', views.booking_create_view, name='booking_create'),
    path('bookings/<int:pk>/', views.booking_detail_view, name='booking_detail'),
    path('bookings/<int:pk>/edit/', views.booking_edit_view, name='booking_edit'),
    path('bookings/<int:pk>/cancel/', views.booking_cancel_view, name='booking_cancel'),
    path('bookings/<int:pk>/status/', views.booking_status_update_view, name='booking_status_update'),
    path('bookings/<int:pk>/receipt/', views.booking_receipt_view, name='booking_receipt'),

    # Предзаказ бара (CRUD позиции бара)
    path('bookings/<int:booking_id>/preorder/add/', views.preorder_add_view, name='preorder_add'),
    path('preorders/<int:item_id>/delete/', views.preorder_delete_view, name='preorder_delete'),

    # Отзывы
    path('bookings/<int:booking_id>/review/', views.review_create_view, name='review_create'),

    # Дашборд и аналитика
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/export-csv/', views.export_bookings_csv_view, name='export_csv'),

    # JSON API (fetch)
    path('api/calculate-price/', views.api_calculate_price_view, name='api_calculate_price'),
    path('api/zones-status/', views.api_zones_status_view, name='api_zones_status'),
]
