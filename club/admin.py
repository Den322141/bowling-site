from django.contrib import admin
from .models import (
    GameType, PlayZone, TariffRate, ClubCard,
    UserProfile, MenuItem, Booking, PreorderItem, Payment, Review
)


class PreorderItemInline(admin.TabularInline):
    model = PreorderItem
    extra = 1
    autocomplete_fields = ['menu_item']


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(GameType)
class GameTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'slug', 'max_players_per_unit', 'is_bowling')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(PlayZone)
class PlayZoneAdmin(admin.ModelAdmin):
    list_display = ('title', 'game_type', 'number', 'status', 'is_vip')
    list_filter = ('game_type', 'status', 'is_vip')
    search_fields = ('title', 'number')


@admin.register(TariffRate)
class TariffRateAdmin(admin.ModelAdmin):
    list_display = ('game_type', 'day_type', 'day_rate_per_hour', 'night_rate_per_hour', 'night_start_hour')
    list_filter = ('game_type', 'day_type')


@admin.register(ClubCard)
class ClubCardAdmin(admin.ModelAdmin):
    list_display = ('card_number', 'card_holder_name', 'phone', 'discount_percent', 'is_active', 'created_at')
    list_filter = ('is_active', 'discount_percent')
    search_fields = ('card_number', 'card_holder_name', 'phone')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'club_card')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__first_name', 'phone')


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'price', 'weight_volume', 'is_available')
    list_filter = ('category', 'is_available')
    search_fields = ('title', 'description')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'booking_number', 'user', 'game_type', 'date',
        'start_time', 'end_time', 'guests_count',
        'total_cost', 'status', 'created_at'
    )
    list_filter = ('status', 'game_type', 'date')
    search_fields = ('booking_number', 'user__username', 'user__first_name')
    filter_horizontal = ('zones',)
    inlines = [PreorderItemInline, PaymentInline]


@admin.register(PreorderItem)
class PreorderItemAdmin(admin.ModelAdmin):
    list_display = ('booking', 'menu_item', 'quantity', 'price_each', 'total_price', 'status')
    list_filter = ('status',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('booking', 'amount', 'payment_method', 'status', 'created_at')
    list_filter = ('status', 'payment_method')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('booking', 'user', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('user__username', 'comment')
