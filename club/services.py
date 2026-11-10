import math
from datetime import datetime, date, time
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from .models import TariffRate, Booking, PlayZone, ClubCard


def get_day_type(check_date: date) -> str:
    """Определяет тип дня: пн-чт (0-3) будни, пт-вс (4-6) выходные."""
    weekday = check_date.weekday()
    return 'weekend' if weekday in [4, 5, 6] else 'weekday'


def calculate_split_hours(start_t: time, end_t: time, night_start_hour: int = 18):
    """
    Рассчитывает количество часов в дневном и вечернем интервале.
    Клуб работает с 10:00 до 02:00.
    Стык тарифов происходит в night_start_hour (по умолчанию 18:00).
    Возвращает (day_hours, night_hours, total_hours).
    """
    start_minutes = start_t.hour * 60 + start_t.minute
    end_minutes = end_t.hour * 60 + end_t.minute

    # Если время окончания меньше времени начала, значит перешли за полночь (например 23:00 - 02:00)
    if end_minutes <= start_minutes:
        end_minutes += 24 * 60

    split_minute = night_start_hour * 60

    day_minutes = 0
    night_minutes = 0

    cur = start_minutes
    while cur < end_minutes:
        next_boundary = min(end_minutes, (cur // 60 + 1) * 60)
        # Интервал [cur, next_boundary)
        hour_of_day = (cur // 60) % 24
        duration = next_boundary - cur

        if 10 <= hour_of_day < night_start_hour:
            day_minutes += duration
        else:
            night_minutes += duration

        cur = next_boundary

    day_hours = Decimal(str(round(day_minutes / 60, 2)))
    night_hours = Decimal(str(round(night_minutes / 60, 2)))
    total_hours = day_hours + night_hours

    return day_hours, night_hours, total_hours


def calculate_booking_pricing(game_type, target_date: date, start_t: time, end_t: time, zones_count: int, club_card=None):
    """
    Полный расчет стоимости игры с учетом стыка дневного и вечернего тарифа,
    количества зон и клубной скидки.
    """
    day_type = get_day_type(target_date)
    tariff = TariffRate.objects.filter(game_type=game_type, day_type=day_type).first()

    if not tariff:
        # Fallback тариф, если не найден
        tariff = TariffRate.objects.filter(game_type=game_type).first()

    day_rate = tariff.day_rate_per_hour if tariff else Decimal('800.00')
    night_rate = tariff.night_rate_per_hour if tariff else Decimal('1400.00')
    night_start = tariff.night_start_hour if tariff else 18

    day_hours, night_hours, total_hours = calculate_split_hours(start_t, end_t, night_start_hour=night_start)

    cost_one_zone = (day_hours * day_rate) + (night_hours * night_rate)
    total_game_cost = cost_one_zone * Decimal(str(max(1, zones_count)))

    discount_percent = Decimal('0.00')
    discount_amount = Decimal('0.00')

    if club_card and club_card.is_active:
        discount_percent = club_card.discount_percent
        discount_amount = round(total_game_cost * (discount_percent / Decimal('100.00')), 2)

    final_game_cost = total_game_cost - discount_amount

    return {
        'day_type': day_type,
        'day_type_display': 'Выходные / Праздники' if day_type == 'weekend' else 'Будние дни',
        'day_rate': day_rate,
        'night_rate': night_rate,
        'night_start': night_start,
        'day_hours': day_hours,
        'night_hours': night_hours,
        'total_hours': total_hours,
        'cost_one_zone': cost_one_zone,
        'zones_count': zones_count,
        'game_cost': total_game_cost,
        'discount_percent': discount_percent,
        'discount_amount': discount_amount,
        'final_game_cost': final_game_cost,
    }


def validate_bowling_capacity(game_type, guests_count: int, zones_count: int):
    """
    Особое требование Варианта 4:
    На одну дорожку допускается компания не более 6 человек, при превышении
    числа гостей система требует добавить в бронь вторую дорожку.
    """
    if getattr(game_type, 'is_bowling', False) or 'боулинг' in game_type.name.lower():
        min_required_lanes = math.ceil(guests_count / 6)
        if zones_count < min_required_lanes:
            raise ValidationError(
                f"На одну дорожку боулинга допускается не более 6 человек. "
                f"Для компании из {guests_count} гостей необходимо выбрать минимум {min_required_lanes} дорожки(-ек)!"
            )


def get_conflicting_zones(zone_ids, target_date: date, start_t: time, end_t: time, exclude_booking_id=None):
    """
    Ищет пересечения бронирований для переданных зон на указанный интервал времени.
    """
    start_min = start_t.hour * 60 + start_t.minute
    end_min = end_t.hour * 60 + end_t.minute
    if end_min <= start_min:
        end_min += 24 * 60

    active_bookings = Booking.objects.filter(
        date=target_date,
        status__in=['pending', 'confirmed', 'completed'],
        zones__id__in=zone_ids
    ).distinct()

    if exclude_booking_id:
        active_bookings = active_bookings.exclude(id=exclude_booking_id)

    conflicting_zone_ids = set()

    for bk in active_bookings:
        b_start_min = bk.start_time.hour * 60 + bk.start_time.minute
        b_end_min = bk.end_time.hour * 60 + bk.end_time.minute
        if b_end_min <= b_start_min:
            b_end_min += 24 * 60

        # Условие пересечения двух временных интервалов: max(start1, start2) < min(end1, end2)
        if max(start_min, b_start_min) < min(end_min, b_end_min):
            for z in bk.zones.all():
                if z.id in zone_ids:
                    conflicting_zone_ids.add(z.id)

    return list(conflicting_zone_ids)


def send_booking_confirmation_email(booking):
    """
    Отправляет уведомление на электронную почту пользователя (пункт 11 общих требований).
    """
    recipient = booking.user.email
    if not recipient:
        return

    zones_list = ", ".join([str(z) for z in booking.zones.all()])
    subject = f"Подтверждение бронирования #{booking.booking_number} в клубе"
    message = f"""Здравствуйте, {booking.user.first_name or booking.user.username}!

Ваше бронирование успешно зарегистрировано:
- Номер брони: {booking.booking_number}
- Тип игры: {booking.game_type.name}
- Выбранные зоны: {zones_list}
- Дата: {booking.date.strftime('%d.%m.%Y')}
- Время: {booking.start_time.strftime('%H:%M')} — {booking.end_time.strftime('%H:%M')} ({booking.hours_total} ч.)
- Количество гостей: {booking.guests_count} чел.
- Стоимость игры: {booking.game_cost} руб.
- Скидка: {booking.discount_amount} руб. ({booking.discount_percent}%)
- Итого к оплате: {booking.total_cost} руб.

Ждём вас в нашем клубе!
Приятного отдыха и отличных страйков!
"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True
        )
    except Exception:
        pass
