import csv
import math
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Sum, Avg, Q, F
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import (
    GameType, PlayZone, TariffRate, ClubCard,
    UserProfile, MenuItem, Booking, PreorderItem, Payment, Review
)
from .forms import (
    UserRegisterForm, UserProfileForm, ClubCardApplyForm,
    BookingForm, PreorderAddForm, ReviewForm
)
from .services import (
    calculate_booking_pricing, validate_bowling_capacity,
    get_conflicting_zones, send_booking_confirmation_email
)


def home_view(request):
    """Главная страница: витрина клуба, типы игр, тарифы, отзывы, интерактивная схема."""
    game_types = GameType.objects.all().prefetch_related('zones', 'tariffs')
    recent_reviews = Review.objects.select_related('user').order_by('-created_at')[:6]
    zones_bowling = PlayZone.objects.filter(game_type__is_bowling=True)
    zones_billiards = PlayZone.objects.filter(game_type__is_bowling=False)
    tariffs = TariffRate.objects.select_related('game_type').all()

    context = {
        'game_types': game_types,
        'recent_reviews': recent_reviews,
        'zones_bowling': zones_bowling,
        'zones_billiards': zones_billiards,
        'tariffs': tariffs,
    }
    return render(request, 'club/home.html', context)


def register_view(request):
    """Регистрация нового посетителя."""
    if request.user.is_authenticated:
        return redirect('booking_list')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.set_password(form.cleaned_data['password'])
                user.save()
                UserProfile.objects.create(
                    user=user,
                    phone=form.cleaned_data['phone'],
                    role='visitor'
                )
            messages.success(request, f"Добро пожаловать, {user.first_name or user.username}! Вы успешно зарегистрированы.")
            login(request, user)
            return redirect('booking_list')
    else:
        form = UserRegisterForm()

    return render(request, 'club/auth/register.html', {'form': form})


@login_required
def profile_view(request):
    """Профиль пользователя: личные данные, клубная карта, смена пароля."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            form = UserProfileForm(request.POST, request.FILES, instance=profile)
            pwd_form = PasswordChangeForm(request.user)
            if form.is_valid():
                form.save()
                messages.success(request, "Профиль успешно обновлён.")
                return redirect('profile')
        elif 'change_password' in request.POST:
            form = UserProfileForm(instance=profile)
            pwd_form = PasswordChangeForm(request.user, request.POST)
            if pwd_form.is_valid():
                user = pwd_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Пароль успешно изменён.")
                return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)
        pwd_form = PasswordChangeForm(request.user)

    card_form = ClubCardApplyForm()

    context = {
        'profile': profile,
        'form': form,
        'pwd_form': pwd_form,
        'card_form': card_form,
    }
    return render(request, 'club/profile.html', context)


@login_required
def apply_club_card_view(request):
    """Привязка клубной карты к профилю."""
    if request.method == 'POST':
        form = ClubCardApplyForm(request.POST)
        if form.is_valid():
            card = form.cleaned_data['card']
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.club_card = card
            profile.save()
            messages.success(request, f"Клубная карта {card.card_number} со скидкой {card.discount_percent}% успешно привязана!")
        else:
            for error in form.errors.values():
                messages.error(request, error)
    return redirect('profile')


# ==============================================================
# КАТАЛОГ МЕНЮ БАРА (Фильтры, Сортировка, Поиск, Пагинация 20)
# ==============================================================

def menu_catalog_view(request):
    """Каталог меню бара и закусок с полнотекстовым поиском, 3 фильтрами, сортировкой по 3 полям и пагинацией по 20 записей."""
    queryset = MenuItem.objects.all()

    # 1. Поиск по тексту
    q = request.GET.get('q', '').strip()
    if q:
        queryset = queryset.filter(Q(title__icontains=q) | Q(description__icontains=q))

    # 2. Фильтр 1: Категория
    category = request.GET.get('category', '').strip()
    if category:
        queryset = queryset.filter(category=category)

    # 3. Фильтр 2: Только в наличии
    in_stock = request.GET.get('in_stock', '').strip()
    if in_stock == '1':
        queryset = queryset.filter(is_available=True)

    # 4. Фильтр 3: Диапазон цен (мин/макс)
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    if min_price:
        try:
            queryset = queryset.filter(price__gte=Decimal(min_price))
        except Exception:
            pass
    if max_price:
        try:
            queryset = queryset.filter(price__lte=Decimal(max_price))
        except Exception:
            pass

    # 5. Сортировка по 3 полям
    sort = request.GET.get('sort', 'category')
    sort_options = {
        'price_asc': 'price',
        'price_desc': '-price',
        'title': 'title',
        'category': 'category',
    }
    order_field = sort_options.get(sort, 'title')
    queryset = queryset.order_by(order_field)

    # 6. Пагинация по 20 записей
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Сохранение параметров в строке запроса для пагинатора
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    extra_params = query_params.urlencode()

    context = {
        'page_obj': page_obj,
        'q': q,
        'category': category,
        'in_stock': in_stock,
        'min_price': min_price,
        'max_price': max_price,
        'sort': sort,
        'extra_params': extra_params,
        'categories': MenuItem.CATEGORY_CHOICES,
        'total_count': queryset.count(),
    }
    return render(request, 'club/menu_catalog.html', context)


# ==============================================================
# БРОНИРОВАНИЕ (CRUD, Особое требование Варианта 4, atomic)
# ==============================================================

@login_required
def booking_create_view(request):
    """
    Создание бронирования:
    - Проверка особого требования: >6 человек для боулинга требует >= 2 дорожек.
    - Авторасчет стоимости на стыке дневного и вечернего тарифов.
    - Атомарное сохранение (transaction.atomic).
    - Отправка email-уведомления.
    """
    selected_game_id = request.GET.get('game_type')
    initial_game = None
    if selected_game_id:
        initial_game = GameType.objects.filter(id=selected_game_id).first()

    if request.method == 'POST':
        form = BookingForm(request.POST, user=request.user)
        if form.is_valid():
            game_type = form.cleaned_data['game_type']
            target_date = form.cleaned_data['date']
            start_t = form.cleaned_data['start_time']
            end_t = form.cleaned_data['end_time']
            guests = form.cleaned_data['guests_count']
            zones = form.cleaned_data['zones']
            notes = form.cleaned_data['notes']
            club_card = form.cleaned_data.get('verified_card')

            if not club_card and hasattr(request.user, 'profile') and request.user.profile.club_card:
                club_card = request.user.profile.club_card

            # Расчёт стоимости на стыке дневного и вечернего тарифов
            pricing = calculate_booking_pricing(
                game_type=game_type,
                target_date=target_date,
                start_t=start_t,
                end_t=end_t,
                zones_count=len(zones),
                club_card=club_card
            )

            # Генерация уникального номера брони
            unique_num = f"BK-{target_date.strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

            with transaction.atomic():
                booking = Booking.objects.create(
                    user=request.user,
                    booking_number=unique_num,
                    game_type=game_type,
                    date=target_date,
                    start_time=start_t,
                    end_time=end_t,
                    guests_count=guests,
                    club_card=club_card,
                    hours_total=pricing['total_hours'],
                    day_hours=pricing['day_hours'],
                    night_hours=pricing['night_hours'],
                    game_cost=pricing['game_cost'],
                    discount_percent=pricing['discount_percent'],
                    discount_amount=pricing['discount_amount'],
                    preorder_cost=Decimal('0.00'),
                    total_cost=pricing['final_game_cost'],
                    status='pending',
                    notes=notes
                )
                booking.zones.set(zones)

                # Создаем предварительную запись оплаты
                Payment.objects.create(
                    booking=booking,
                    amount=booking.total_cost,
                    payment_method='card',
                    status='completed',
                    transaction_id=f"TXN-{uuid.uuid4().hex[:8].upper()}"
                )

            # Отправка уведомления на email
            send_booking_confirmation_email(booking)

            messages.success(
                request,
                f"Бронирование #{booking.booking_number} успешно создано! Итоговая стоимость: {booking.total_cost} руб."
            )
            return redirect('booking_detail', pk=booking.pk)
    else:
        initial = {}
        if initial_game:
            initial['game_type'] = initial_game
        initial['date'] = date.today()
        initial['start_time'] = time(14, 0)
        initial['end_time'] = time(16, 0)
        initial['guests_count'] = 4
        form = BookingForm(initial=initial, user=request.user)

    zones_json = [
        {'id': z.id, 'game_type_id': z.game_type_id, 'number': z.number, 'title': z.title, 'is_vip': z.is_vip}
        for z in PlayZone.objects.filter(status='available')
    ]

    context = {
        'form': form,
        'zones_json': zones_json,
    }
    return render(request, 'club/booking_form.html', context)


@login_required
def booking_list_view(request):
    """
    Список бронирований:
    - Обычный пользователь видит ТОЛЬКО свои бронирования (пункт 4).
    - Персонал (operator, admin) видит все бронирования клуба.
    - Фильтрация по статусу, дате, типу игры, поиск по номеру, сортировка и пагинация по 20 записей.
    """
    is_staff = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ['operator', 'admin', 'bar_manager']
    )

    if is_staff:
        queryset = Booking.objects.all().select_related('user', 'game_type', 'club_card').prefetch_related('zones')
    else:
        queryset = Booking.objects.filter(user=request.user).select_related('game_type', 'club_card').prefetch_related('zones')

    # Поиск
    q = request.GET.get('q', '').strip()
    if q:
        queryset = queryset.filter(
            Q(booking_number__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__first_name__icontains=q)
        )

    # Фильтры
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    game_filter = request.GET.get('game_type', '').strip()
    if game_filter:
        queryset = queryset.filter(game_type_id=game_filter)

    date_filter = request.GET.get('date', '').strip()
    if date_filter:
        try:
            queryset = queryset.filter(date=date_filter)
        except Exception:
            pass

    # Сортировка
    sort = request.GET.get('sort', 'newest')
    sort_dict = {
        'newest': '-date',
        'oldest': 'date',
        'cost_desc': '-total_cost',
        'cost_asc': 'total_cost',
    }
    queryset = queryset.order_by(sort_dict.get(sort, '-date'), '-start_time')

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    extra_params = query_params.urlencode()

    context = {
        'page_obj': page_obj,
        'is_staff': is_staff,
        'statuses': Booking.STATUS_CHOICES,
        'game_types': GameType.objects.all(),
        'status_filter': status_filter,
        'game_filter': game_filter,
        'date_filter': date_filter,
        'sort': sort,
        'q': q,
        'extra_params': extra_params,
    }
    return render(request, 'club/booking_list.html', context)


@login_required
def booking_detail_view(request, pk):
    """
    Детальный просмотр бронирования:
    - Проверка прав: чужой пользователь получает 403 Forbidden (пункт 4).
    - Список дорожек, финансовая детализация со стыком тарифов.
    - Предзаказ закусок и напитков.
    - Форма добавления блюда в предзаказ.
    """
    booking = get_object_or_404(
        Booking.objects.select_related('user', 'game_type', 'club_card').prefetch_related('zones', 'preorders__menu_item'),
        pk=pk
    )

    is_staff = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ['operator', 'admin', 'bar_manager']
    )

    if not is_staff and booking.user != request.user:
        return HttpResponseForbidden("У вас нет прав для просмотра этого бронирования.")

    preorder_form = PreorderAddForm()
    review_form = ReviewForm()

    context = {
        'booking': booking,
        'preorders': booking.preorders.all(),
        'preorder_form': preorder_form,
        'review_form': review_form,
        'is_staff': is_staff,
    }
    return render(request, 'club/booking_detail.html', context)


@login_required
def booking_edit_view(request, pk):
    """
    Редактирование бронирования:
    - Полный цикл изменения данных бронирования пользователем.
    - Пересчет тарифов на стыке времени и проверка вместимости дорожек.
    """
    booking = get_object_or_404(Booking, pk=pk)
    is_staff = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ['operator', 'admin']
    )

    if not is_staff and booking.user != request.user:
        return HttpResponseForbidden("Вы можете редактировать только свои бронирования.")

    if booking.status in ['completed', 'cancelled']:
        messages.warning(request, "Нельзя редактировать завершённое или отменённое бронирование.")
        return redirect('booking_detail', pk=booking.pk)

    if request.method == 'POST':
        form = BookingForm(request.POST, instance=booking, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                updated_booking = form.save(commit=False)
                zones = form.cleaned_data['zones']
                club_card = form.cleaned_data.get('verified_card') or booking.club_card

                pricing = calculate_booking_pricing(
                    game_type=updated_booking.game_type,
                    target_date=updated_booking.date,
                    start_t=updated_booking.start_time,
                    end_t=updated_booking.end_time,
                    zones_count=len(zones),
                    club_card=club_card
                )

                updated_booking.hours_total = pricing['total_hours']
                updated_booking.day_hours = pricing['day_hours']
                updated_booking.night_hours = pricing['night_hours']
                updated_booking.game_cost = pricing['game_cost']
                updated_booking.discount_percent = pricing['discount_percent']
                updated_booking.discount_amount = pricing['discount_amount']
                updated_booking.club_card = club_card
                updated_booking.total_cost = (pricing['game_cost'] - pricing['discount_amount']) + updated_booking.preorder_cost
                updated_booking.save()
                updated_booking.zones.set(zones)

            messages.success(request, f"Бронирование #{booking.booking_number} успешно обновлено.")
            return redirect('booking_detail', pk=booking.pk)
    else:
        form = BookingForm(instance=booking, user=request.user)

    context = {
        'form': form,
        'booking': booking,
    }
    return render(request, 'club/booking_edit.html', context)


@login_required
@require_POST
def booking_cancel_view(request, pk):
    """Отмена бронирования (Delete/Cancel цикл)."""
    booking = get_object_or_404(Booking, pk=pk)
    is_staff = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ['operator', 'admin']
    )

    if not is_staff and booking.user != request.user:
        return HttpResponseForbidden("Вы можете отменять только свои бронирования.")

    booking.status = 'cancelled'
    booking.save(update_fields=['status'])
    messages.info(request, f"Бронирование #{booking.booking_number} успешно отменено.")
    return redirect('booking_detail', pk=booking.pk)


@login_required
@require_POST
def booking_status_update_view(request, pk):
    """Смена статуса бронирования оператором или администратором."""
    is_staff = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ['operator', 'admin']
    )
    if not is_staff:
        return HttpResponseForbidden("Только персонал может менять статус бронирования.")

    booking = get_object_or_404(Booking, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(Booking.STATUS_CHOICES):
        booking.status = new_status
        booking.save(update_fields=['status'])
        messages.success(request, f"Статус бронирования #{booking.booking_number} изменён на: {booking.get_status_display()}")
    return redirect('booking_detail', pk=booking.pk)


# ==============================================================
# ПРЕДЗАКАЗ В БАР (CRUD второй сущности)
# ==============================================================

@login_required
@require_POST
def preorder_add_view(request, booking_id):
    """Добавление позиции бара в бронирование с пересчетом итоговой суммы в transaction.atomic."""
    booking = get_object_or_404(Booking, pk=booking_id)

    is_staff = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ['bar_manager', 'operator', 'admin']
    )
    if not is_staff and booking.user != request.user:
        return HttpResponseForbidden("Вы не можете добавлять блюда к чужому бронированию.")

    form = PreorderAddForm(request.POST)
    if form.is_valid():
        menu_item = form.cleaned_data['menu_item']
        quantity = form.cleaned_data['quantity']

        with transaction.atomic():
            preorder_item = PreorderItem.objects.create(
                booking=booking,
                menu_item=menu_item,
                quantity=quantity,
                price_each=menu_item.price,
                total_price=menu_item.price * quantity,
                status='ordered'
            )
            booking.update_preorder_totals()

        messages.success(request, f"«{menu_item.title}» ({quantity} шт.) добавлено в заказ к дорожке!")
    else:
        messages.error(request, "Ошибка при добавлении блюда в предзаказ.")

    return redirect('booking_detail', pk=booking.pk)


@login_required
@require_POST
def preorder_delete_view(request, item_id):
    """Удаление позиции из предзаказа бара с пересчетом итоговой суммы."""
    preorder_item = get_object_or_404(PreorderItem.objects.select_related('booking'), pk=item_id)
    booking = preorder_item.booking

    is_staff = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ['bar_manager', 'operator', 'admin']
    )
    if not is_staff and booking.user != request.user:
        return HttpResponseForbidden("Вы не можете удалять позиции из чужого заказа.")

    with transaction.atomic():
        item_title = preorder_item.menu_item.title
        preorder_item.delete()
        booking.update_preorder_totals()

    messages.info(request, f"Позиция «{item_title}» удалена из предзаказа.")
    return redirect('booking_detail', pk=booking.pk)


@login_required
@require_POST
def review_create_view(request, booking_id):
    """Оставление отзыва по бронированию."""
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.user != request.user:
        return HttpResponseForbidden("Вы можете оставить отзыв только по своему бронированию.")

    if hasattr(booking, 'review'):
        messages.warning(request, "Вы уже оставили отзыв к этому бронированию.")
        return redirect('booking_detail', pk=booking.pk)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.booking = booking
        review.user = request.user
        review.save()
        messages.success(request, "Спасибо за ваш отзыв!")
    return redirect('booking_detail', pk=booking.pk)


# ==============================================================
# ПЕЧАТНАЯ ФОРМА И CSV ЭКСПОРТ (Пункт 10)
# ==============================================================

@login_required
def booking_receipt_view(request, pk):
    """Печатная форма талона-квитанции бронирования для распечатки на кассе или посетителем."""
    booking = get_object_or_404(
        Booking.objects.select_related('user', 'game_type', 'club_card').prefetch_related('zones', 'preorders__menu_item'),
        pk=pk
    )

    is_staff = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ['operator', 'admin', 'bar_manager']
    )
    if not is_staff and booking.user != request.user:
        return HttpResponseForbidden("Нет доступа к квитанции чужого бронирования.")

    context = {
        'booking': booking,
        'preorders': booking.preorders.all(),
        'print_time': timezone.now(),
    }
    return render(request, 'club/booking_receipt.html', context)


@login_required
def export_bookings_csv_view(request):
    """Экспорт реестра бронирований в формате CSV с кодировкой UTF-8 BOM для Microsoft Excel."""
    is_staff = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ['operator', 'admin']
    )
    if not is_staff:
        # Обычный пользователь может экспортировать только свои брони
        bookings = Booking.objects.filter(user=request.user).select_related('game_type', 'club_card').prefetch_related('zones')
    else:
        bookings = Booking.objects.all().select_related('user', 'game_type', 'club_card').prefetch_related('zones')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="bowling_bookings_{date.today().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Номер брони', 'Пользователь', 'Тип игры', 'Зоны / Дорожки', 'Дата игры',
        'Время начала', 'Время окончания', 'Всего часов', 'Дневных часов',
        'Вечерних часов', 'Гостей', 'Стоимость игры (руб)', 'Скидка (руб)',
        'Бар (руб)', 'Итого (руб)', 'Статус', 'Дата создания'
    ])

    for b in bookings:
        zones_str = ", ".join([f"{z.title} #{z.number}" for z in b.zones.all()])
        writer.writerow([
            b.booking_number,
            b.user.username,
            b.game_type.name,
            zones_str,
            b.date.strftime('%d.%m.%Y'),
            b.start_time.strftime('%H:%M'),
            b.end_time.strftime('%H:%M'),
            b.hours_total,
            b.day_hours,
            b.night_hours,
            b.guests_count,
            b.game_cost,
            b.discount_amount,
            b.preorder_cost,
            b.total_cost,
            b.get_status_display(),
            b.created_at.strftime('%d.%m.%Y %H:%M')
        ])

    return response


# ==============================================================
# СВОДНЫЕ ПОКАЗАТЕЛИ И ДАШБОРД (Пункт 7: count, sum, avg, ratio + диаграмма)
# ==============================================================

@login_required
def dashboard_view(request):
    """
    Страница со сводными показателями клуба (пункт 7):
    - Не менее четырёх агрегатных значений:
      1) Общее количество бронирований (Count)
      2) Общая выручка клуба (Sum)
      3) Средний чек бронирования (Avg)
      4) Доля бронирований с клубной картой (Ratio)
    - Статистика по типам игр
    - Данные для HTML5 диаграммы популярности дорожек по часам
    """
    is_staff = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ['operator', 'admin', 'bar_manager']
    )
    if not is_staff:
        # Для обычного посетителя показываем его персональную статистику
        bookings_qs = Booking.objects.filter(user=request.user)
    else:
        bookings_qs = Booking.objects.all()

    # 1. Агрегатные запросы
    total_bookings = bookings_qs.count()
    completed_bookings = bookings_qs.filter(status__in=['confirmed', 'completed']).count()
    revenue_agg = bookings_qs.filter(status__in=['confirmed', 'completed']).aggregate(
        total_revenue=Sum('total_cost'),
        avg_check=Avg('total_cost'),
        total_hours=Sum('hours_total'),
        avg_guests=Avg('guests_count')
    )
    total_revenue = revenue_agg['total_revenue'] or Decimal('0.00')
    avg_check = round(revenue_agg['avg_check'] or Decimal('0.00'), 2)
    avg_guests = round(revenue_agg['avg_guests'] or 0, 1)

    # 2. Доля (Ratio): процент бронирований с применением клубной карты
    card_bookings_count = bookings_qs.filter(club_card__isnull=False).count()
    card_ratio = round((card_bookings_count / total_bookings * 100), 1) if total_bookings > 0 else 0

    # 3. Распределение по типам игр
    game_stats = bookings_qs.values('game_type__name', 'game_type__icon').annotate(
        count=Count('id'),
        revenue=Sum('total_cost')
    ).order_by('-count')

    # 4. Распределение бронирований по часам начала для диаграммы
    hours_labels = [f"{h:02d}:00" for h in range(10, 24)]
    hours_counts = []
    for h in range(10, 24):
        c = bookings_qs.filter(start_time__hour=h).count()
        hours_counts.append(c)

    # 5. Последние 10 бронирований
    recent_bookings = bookings_qs.select_related('user', 'game_type').order_by('-created_at')[:10]

    context = {
        'total_bookings': total_bookings,
        'completed_bookings': completed_bookings,
        'total_revenue': total_revenue,
        'avg_check': avg_check,
        'avg_guests': avg_guests,
        'card_ratio': card_ratio,
        'card_bookings_count': card_bookings_count,
        'game_stats': game_stats,
        'hours_labels': hours_labels,
        'hours_counts': hours_counts,
        'recent_bookings': recent_bookings,
        'is_staff': is_staff,
    }
    return render(request, 'club/dashboard.html', context)


# ==============================================================
# JSON API ДЛЯ FETCH ЗАПРОСОВ (Пункт 8)
# ==============================================================

@require_GET
def api_calculate_price_view(request):
    """
    JSON API для динамического расчёта стоимости при оформлении бронирования без перезагрузки:
    Возвращает разбивку дневных и вечерних часов на стыке, стоимость и скидку.
    """
    try:
        game_type_id = request.GET.get('game_type_id')
        date_str = request.GET.get('date')
        start_str = request.GET.get('start_time')
        end_str = request.GET.get('end_time')
        zones_count = int(request.GET.get('zones_count', 1))
        guests_count = int(request.GET.get('guests_count', 2))
        card_code = request.GET.get('card_code', '').strip()

        if not (game_type_id and date_str and start_str and end_str):
            return JsonResponse({'error': 'Не все обязательные параметры переданы'}, status=400)

        game_type = get_object_or_404(GameType, pk=game_type_id)
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Парсинг времени "HH:MM"
        s_parts = [int(p) for p in start_str.split(':')[:2]]
        e_parts = [int(p) for p in end_str.split(':')[:2]]
        start_t = time(s_parts[0], s_parts[1])
        end_t = time(e_parts[0], e_parts[1])

        # Проверка клубной карты
        club_card = None
        if card_code:
            club_card = ClubCard.objects.filter(card_number__iexact=card_code, is_active=True).first()
        elif request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.club_card:
            club_card = request.user.profile.club_card

        pricing = calculate_booking_pricing(
            game_type=game_type,
            target_date=target_date,
            start_t=start_t,
            end_t=end_t,
            zones_count=zones_count,
            club_card=club_card
        )

        # Особое требование Варианта 4
        bowling_warning = None
        if game_type.is_bowling:
            min_lanes = math.ceil(guests_count / 6)
            if zones_count < min_lanes:
                bowling_warning = (
                    f"На одну дорожку боулинга допускается до 6 человек. "
                    f"Для компании из {guests_count} гостей требуется минимум {min_lanes} дорожки(-ек)!"
                )

        return JsonResponse({
            'success': True,
            'day_type': pricing['day_type'],
            'day_type_display': pricing['day_type_display'],
            'day_rate': float(pricing['day_rate']),
            'night_rate': float(pricing['night_rate']),
            'night_start': pricing['night_start'],
            'day_hours': float(pricing['day_hours']),
            'night_hours': float(pricing['night_hours']),
            'total_hours': float(pricing['total_hours']),
            'cost_one_zone': float(pricing['cost_one_zone']),
            'zones_count': pricing['zones_count'],
            'game_cost': float(pricing['game_cost']),
            'discount_percent': float(pricing['discount_percent']),
            'discount_amount': float(pricing['discount_amount']),
            'final_game_cost': float(pricing['final_game_cost']),
            'bowling_warning': bowling_warning,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_GET
def api_zones_status_view(request):
    """
    JSON API для интерактивной схемы зала:
    Возвращает список всех зон и статус занятости на выбранный интервал.
    """
    try:
        date_str = request.GET.get('date')
        start_str = request.GET.get('start_time')
        end_str = request.GET.get('end_time')
        game_type_id = request.GET.get('game_type_id')

        zones_qs = PlayZone.objects.all().select_related('game_type')
        if game_type_id:
            zones_qs = zones_qs.filter(game_type_id=game_type_id)

        busy_zone_ids = set()
        if date_str and start_str and end_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            s_parts = [int(p) for p in start_str.split(':')[:2]]
            e_parts = [int(p) for p in end_str.split(':')[:2]]
            start_t = time(s_parts[0], s_parts[1])
            end_t = time(e_parts[0], e_parts[1])

            all_ids = list(zones_qs.values_list('id', flat=True))
            busy_zone_ids = set(get_conflicting_zones(all_ids, target_date, start_t, end_t))

        zones_data = []
        for z in zones_qs:
            is_busy = z.id in busy_zone_ids
            zones_data.append({
                'id': z.id,
                'game_type_id': z.game_type_id,
                'game_name': z.game_type.name,
                'number': z.number,
                'title': z.title,
                'status': 'busy' if is_busy else z.status,
                'is_vip': z.is_vip,
                'photo_url': z.photo.url if z.photo else '',
            })

        return JsonResponse({'success': True, 'zones': zones_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
