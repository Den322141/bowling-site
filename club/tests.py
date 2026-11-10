import math
from datetime import date, time, timedelta
from decimal import Decimal

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse

from .models import (
    GameType, PlayZone, TariffRate, ClubCard,
    UserProfile, MenuItem, Booking, PreorderItem
)
from .services import calculate_booking_pricing, validate_bowling_capacity


class BowlingClubTestCase(TestCase):
    def setUp(self):
        # 1. Пользователи
        self.user1 = User.objects.create_user(username='client1', password='pass123', email='c1@test.com')
        self.profile1 = UserProfile.objects.create(user=self.user1, phone='+79991112233', role='visitor')

        self.user2 = User.objects.create_user(username='client2', password='pass123', email='c2@test.com')
        self.profile2 = UserProfile.objects.create(user=self.user2, phone='+79992223344', role='visitor')

        self.admin_user = User.objects.create_superuser(username='admin_test', password='adminpass', email='admin@test.com')
        self.admin_profile = UserProfile.objects.create(user=self.admin_user, phone='+79990000000', role='admin')

        # 2. Клубная карта
        self.card = ClubCard.objects.create(
            card_number='CLUB-TEST-10',
            card_holder_name='Тестовый Клиент',
            phone='+79991112233',
            discount_percent=Decimal('10.00'),
            is_active=True
        )
        self.profile1.club_card = self.card
        self.profile1.save()

        # 3. Типы игр
        self.gt_bowling = GameType.objects.create(
            name='Боулинг',
            slug='bowling',
            max_players_per_unit=6,
            is_bowling=True,
            icon='🎳'
        )
        self.gt_billiards = GameType.objects.create(
            name='Русский бильярд',
            slug='billiards',
            max_players_per_unit=4,
            is_bowling=False,
            icon='🎱'
        )

        # 4. Дорожки и столы
        self.lane1 = PlayZone.objects.create(game_type=self.gt_bowling, number=1, title='Дорожка 1')
        self.lane2 = PlayZone.objects.create(game_type=self.gt_bowling, number=2, title='Дорожка 2')
        self.table1 = PlayZone.objects.create(game_type=self.gt_billiards, number=1, title='Стол 1')

        # 5. Тарифы: День (10:00-18:00) 800 руб/ч, Вечер (18:00-02:00) 1400 руб/ч
        self.tariff_bowling = TariffRate.objects.create(
            game_type=self.gt_bowling,
            day_type='weekday',
            day_rate_per_hour=Decimal('800.00'),
            night_rate_per_hour=Decimal('1400.00'),
            day_start_hour=10,
            night_start_hour=18,
            night_end_hour=2
        )

        # 6. Меню бара
        self.pizza = MenuItem.objects.create(
            category='hot',
            title='Пицца Тест',
            price=Decimal('500.00'),
            weight_volume='500 г'
        )

    def test_special_requirement_bowling_capacity(self):
        """Проверка особого требования: максимум 6 чел на дорожку, >6 требует >=2 дорожек."""
        # 1. Компания из 5 человек на 1 дорожку — проходит
        try:
            validate_bowling_capacity(self.gt_bowling, guests_count=5, zones_count=1)
        except ValidationError:
            self.fail("Компания из 5 человек должна помещаться на 1 дорожку!")

        # 2. Компания из 8 человек на 1 дорожку — ДОЛЖНО вызывать ошибку!
        with self.assertRaises(ValidationError):
            validate_bowling_capacity(self.gt_bowling, guests_count=8, zones_count=1)

        # 3. Компания из 8 человек на 2 дорожки — проходит
        try:
            validate_bowling_capacity(self.gt_bowling, guests_count=8, zones_count=2)
        except ValidationError:
            self.fail("Компания из 8 человек должна быть разрешена на 2 дорожках!")

    def test_special_requirement_split_pricing(self):
        """Проверка автоматического расчета стоимости на стыке дневного (800) и вечернего (1400) тарифов."""
        # Бронь в будний день (например, вторник) с 16:00 до 20:00 (длительность 4 часа)
        # С 16:00 до 18:00 — 2 часа дневных (2 * 800 = 1600)
        # С 18:00 до 20:00 — 2 часа вечерних (2 * 1400 = 2800)
        # Итого за 1 дорожку: 1600 + 2800 = 4400 руб.
        # Со скидкой карты 10%: 4400 - 440 = 3960 руб.
        test_tuesday = date(2026, 11, 10) # Вторник
        pricing = calculate_booking_pricing(
            game_type=self.gt_bowling,
            target_date=test_tuesday,
            start_t=time(16, 0),
            end_t=time(20, 0),
            zones_count=1,
            club_card=self.card
        )

        self.assertEqual(pricing['day_hours'], Decimal('2.00'))
        self.assertEqual(pricing['night_hours'], Decimal('2.00'))
        self.assertEqual(pricing['total_hours'], Decimal('4.00'))
        self.assertEqual(pricing['game_cost'], Decimal('4400.00'))
        self.assertEqual(pricing['discount_amount'], Decimal('440.00'))
        self.assertEqual(pricing['final_game_cost'], Decimal('3960.00'))

    def test_access_restriction_user_cannot_view_others_booking(self):
        """Пункт 4: Попытка открыть чужую страницу возвращает ошибку доступа (403 Forbidden)."""
        client = Client()
        client.force_login(self.user1)

        # Создаем бронь пользователя 2
        booking2 = Booking.objects.create(
            user=self.user2,
            booking_number='BK-TEST-USER2',
            game_type=self.gt_billiards,
            date=date.today() + timedelta(days=1),
            start_time=time(14, 0),
            end_time=time(16, 0),
            guests_count=2,
            total_cost=Decimal('1200.00'),
            status='confirmed'
        )
        booking2.zones.add(self.table1)

        # Пользователь 1 пытается открыть детальную страницу чужой брони
        url = reverse('booking_detail', kwargs={'pk': booking2.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_api_calculate_price_fetch(self):
        """Пункт 8: fetch запрос к собственному JSON представлению."""
        client = Client()
        url = reverse('api_calculate_price')
        response = client.get(url, {
            'game_type_id': self.gt_bowling.id,
            'date': '2026-11-10',
            'start_time': '16:00',
            'end_time': '20:00',
            'zones_count': 1,
            'guests_count': 4,
            'card_code': 'CLUB-TEST-10'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['day_hours'], 2.0)
        self.assertEqual(data['night_hours'], 2.0)
        self.assertEqual(data['final_game_cost'], 3960.0)

    def test_crud_preorder_and_transaction(self):
        """CRUD второй сущности (предзаказ бара) и пересчет итоговой стоимости."""
        client = Client()
        client.force_login(self.user1)

        booking = Booking.objects.create(
            user=self.user1,
            booking_number='BK-TEST-CRUD',
            game_type=self.gt_bowling,
            date=date.today() + timedelta(days=1),
            start_time=time(14, 0),
            end_time=time(16, 0),
            guests_count=4,
            game_cost=Decimal('1600.00'),
            total_cost=Decimal('1600.00'),
            status='pending'
        )
        booking.zones.add(self.lane1)

        # Добавление позиции предзаказа
        add_url = reverse('preorder_add', kwargs={'booking_id': booking.pk})
        res = client.post(add_url, {'menu_item': self.pizza.id, 'quantity': 2})
        self.assertEqual(res.status_code, 302)

        booking.refresh_from_db()
        self.assertEqual(booking.preorders.count(), 1)
        self.assertEqual(booking.preorder_cost, Decimal('1000.00')) # 2 * 500 = 1000
        self.assertEqual(booking.total_cost, Decimal('2600.00')) # 1600 + 1000 = 2600

        # Удаление позиции
        item = booking.preorders.first()
        del_url = reverse('preorder_delete', kwargs={'item_id': item.id})
        res_del = client.post(del_url)
        self.assertEqual(res_del.status_code, 302)

        booking.refresh_from_db()
        self.assertEqual(booking.preorders.count(), 0)
        self.assertEqual(booking.total_cost, Decimal('1600.00'))
