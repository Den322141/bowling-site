import random
import uuid
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from club.models import (
    GameType, PlayZone, TariffRate, ClubCard,
    UserProfile, MenuItem, Booking, PreorderItem, Payment, Review
)
from club.services import calculate_booking_pricing


class Command(BaseCommand):
    help = "Заполнение базы данных демонстрационными данными (требование: >=30 бронирований, >=10 связанных записей)"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Очистка и генерация демонстрационных данных...")

        # 1. Администратор и сотрудники
        admin_user, _ = User.objects.get_or_create(username='admin', defaults={'first_name': 'Администратор', 'email': 'admin@strike-club.ru', 'is_staff': True, 'is_superuser': True})
        admin_user.set_password('admin123')
        admin_user.save()
        UserProfile.objects.update_or_create(user=admin_user, defaults={'role': 'admin', 'phone': '+7 (900) 111-22-33'})

        op_user, _ = User.objects.get_or_create(username='operator', defaults={'first_name': 'Алексей (Оператор)', 'email': 'operator@strike-club.ru', 'is_staff': True})
        op_user.set_password('operator123')
        op_user.save()
        UserProfile.objects.update_or_create(user=op_user, defaults={'role': 'operator', 'phone': '+7 (900) 222-33-44'})

        bar_user, _ = User.objects.get_or_create(username='barman', defaults={'first_name': 'Михаил (Бармен)', 'email': 'bar@strike-club.ru', 'is_staff': True})
        bar_user.set_password('barman123')
        bar_user.save()
        UserProfile.objects.update_or_create(user=bar_user, defaults={'role': 'bar_manager', 'phone': '+7 (900) 333-44-55'})

        # Клиенты
        client_names = [
            ('ivan', 'Иван Смирнов', 'ivan@mail.ru', '+7 (916) 100-20-30'),
            ('elena', 'Елена Кузнецова', 'elena@yandex.ru', '+7 (916) 200-30-40'),
            ('dmitry', 'Дмитрий Попов', 'dmitry@gmail.com', '+7 (916) 300-40-50'),
            ('anna', 'Анна Васильева', 'anna@mail.ru', '+7 (916) 400-50-60'),
            ('sergey', 'Сергей Новиков', 'sergey@inbox.ru', '+7 (916) 500-60-70'),
            ('olga', 'Ольга Морозова', 'olga@list.ru', '+7 (916) 600-70-80'),
            ('artem', 'Артём Волков', 'artem@yandex.ru', '+7 (916) 700-80-90'),
            ('marina', 'Марина Соколова', 'marina@mail.ru', '+7 (916) 800-90-00'),
        ]
        clients = []
        for uname, fname, mail, ph in client_names:
            u, _ = User.objects.get_or_create(username=uname, defaults={'first_name': fname, 'email': mail})
            u.set_password('client123')
            u.save()
            prof, _ = UserProfile.objects.update_or_create(user=u, defaults={'role': 'visitor', 'phone': ph})
            clients.append((u, prof))

        # 2. Клубные карты (10 штук)
        cards_data = [
            ("CLUB-1001", "Иван Смирнов", "+7 (916) 100-20-30", Decimal('10.00')),
            ("CLUB-1002", "Елена Кузнецова", "+7 (916) 200-30-40", Decimal('15.00')),
            ("CLUB-1003", "Дмитрий Попов", "+7 (916) 300-40-50", Decimal('5.00')),
            ("CLUB-1004", "Анна Васильева", "+7 (916) 400-50-60", Decimal('20.00')),
            ("CLUB-1005", "Сергей Новиков", "+7 (916) 500-60-70", Decimal('10.00')),
            ("CLUB-1006", "Ольга Морозова", "+7 (916) 600-70-80", Decimal('10.00')),
            ("CLUB-1007", "Виктор Федоров", "+7 (915) 111-22-33", Decimal('5.00')),
            ("CLUB-1008", "Наталья Ильина", "+7 (915) 222-33-44", Decimal('15.00')),
            ("CLUB-1009", "Константин Кравцов", "+7 (915) 333-44-55", Decimal('20.00')),
            ("CLUB-1010", "Татьяна Орлова", "+7 (915) 444-55-66", Decimal('10.00')),
        ]
        club_cards = []
        for num, holder, ph, disc in cards_data:
            c, _ = ClubCard.objects.update_or_create(
                card_number=num,
                defaults={'card_holder_name': holder, 'phone': ph, 'discount_percent': disc, 'is_active': True}
            )
            club_cards.append(c)

        # Привяжем карты первым клиентам
        for i, card in enumerate(club_cards[:len(clients)]):
            clients[i][1].club_card = card
            clients[i][1].save()

        # 3. Типы игр
        gt_bowling, _ = GameType.objects.update_or_create(
            slug='bowling',
            defaults={
                'name': 'Боулинг',
                'description': 'Современные дорожки с профессиональным покрытием Brunswick и автоматической системой подсчёта очков.',
                'max_players_per_unit': 6,
                'is_bowling': True,
                'icon': '🎳'
            }
        )

        gt_russian, _ = GameType.objects.update_or_create(
            slug='russian-billiards',
            defaults={
                'name': 'Русский бильярд (Пирамида)',
                'description': 'Профессиональные 12-футовые столы из натурального сланца Ардезия и отборного сукна Iwan Simonis.',
                'max_players_per_unit': 4,
                'is_bowling': False,
                'icon': '🎱'
            }
        )

        gt_pool, _ = GameType.objects.update_or_create(
            slug='american-pool',
            defaults={
                'name': 'Американский пул',
                'description': 'Динамичная и увлекательная игра на 9-футовых столах Dynamic II с качественными шарами Aramith.',
                'max_players_per_unit': 4,
                'is_bowling': False,
                'icon': '🎱'
            }
        )

        gt_snooker, _ = GameType.objects.update_or_create(
            slug='snooker',
            defaults={
                'name': 'Снукер',
                'description': 'Классический английский снукер на элитном полноразмерном столе с подогревом плиты.',
                'max_players_per_unit': 4,
                'is_bowling': False,
                'icon': '🎯'
            }
        )

        # 4. Тарифная сетка (будни / выходные, стык дневного и вечернего в 18:00)
        tariffs = [
            (gt_bowling, 'weekday', Decimal('750.00'), Decimal('1200.00')),
            (gt_bowling, 'weekend', Decimal('1100.00'), Decimal('1650.00')),
            (gt_russian, 'weekday', Decimal('600.00'), Decimal('950.00')),
            (gt_russian, 'weekend', Decimal('850.00'), Decimal('1300.00')),
            (gt_pool, 'weekday', Decimal('500.00'), Decimal('800.00')),
            (gt_pool, 'weekend', Decimal('700.00'), Decimal('1100.00')),
            (gt_snooker, 'weekday', Decimal('700.00'), Decimal('1100.00')),
            (gt_snooker, 'weekend', Decimal('950.00'), Decimal('1450.00')),
        ]
        for gt, dt, day_r, night_r in tariffs:
            TariffRate.objects.update_or_create(
                game_type=gt,
                day_type=dt,
                defaults={
                    'day_rate_per_hour': day_r,
                    'night_rate_per_hour': night_r,
                    'day_start_hour': 10,
                    'night_start_hour': 18,
                    'night_end_hour': 2
                }
            )

        # 5. Игровые зоны (14 зон: 6 дорожек боулинга, 4 русских стола, 3 пула, 1 снукер)
        bowling_zones = []
        for num in range(1, 7):
            is_vip = (num >= 5)
            z, _ = PlayZone.objects.update_or_create(
                game_type=gt_bowling,
                number=num,
                defaults={
                    'title': f'Дорожка №{num}' + (' (VIP Lounge)' if is_vip else ''),
                    'description': 'Детские бортики-бамперы, удобные диваны, мультимедийная анимация страйков.',
                    'status': 'available',
                    'is_vip': is_vip
                }
            )
            bowling_zones.append(z)

        billiard_zones = []
        for num in range(1, 5):
            z, _ = PlayZone.objects.update_or_create(
                game_type=gt_russian,
                number=num,
                defaults={
                    'title': f'Русский стол №{num} (12 футов)',
                    'description': 'Плита Ардезия 45 мм, профессиональный киевник, отдельная зона отдыха.',
                    'status': 'available',
                    'is_vip': (num == 4)
                }
            )
            billiard_zones.append(z)

        for num in range(1, 4):
            z, _ = PlayZone.objects.update_or_create(
                game_type=gt_pool,
                number=num,
                defaults={
                    'title': f'Пул стол №{num} (9 футов)',
                    'description': 'Бельгийское сукно, шары Super Aramith Pro.',
                    'status': 'available',
                    'is_vip': False
                }
            )
            billiard_zones.append(z)

        z_snooker, _ = PlayZone.objects.update_or_create(
            game_type=gt_snooker,
            number=1,
            defaults={
                'title': 'Снукерный стол №1 (Royal Club)',
                'description': 'Элитный стол Riley Aristocrat с подогревом плиты.',
                'status': 'available',
                'is_vip': True
            }
        )
        billiard_zones.append(z_snooker)

        all_zones = bowling_zones + billiard_zones

        # 6. Меню бара и кухни (16 позиций)
        menu_items_data = [
            ('snacks', 'Сырные палочки с клюквенным соусом', 'Хрустящая корочка, нежная моцарелла', Decimal('380.00'), '200 г'),
            ('snacks', 'Гренки чесночные с соусом тар-тар', 'Бородинский хлеб с чесноком и пармезаном', Decimal('290.00'), '180 г'),
            ('snacks', 'Куриные крылышки BBQ', 'Крылышки в карамельной глазури с кунжутом', Decimal('490.00'), '320 г'),
            ('snacks', 'Кесадилья с курицей и перцем', 'Сыр чеддер, филе гриль, соус сальса', Decimal('460.00'), '280 г'),
            ('snacks', 'Начос гранде с сырным соусом и халапеньо', 'Кукурузные чипсы, гуакамоле, сальса', Decimal('390.00'), '250 г'),
            ('hot', 'Пицца «Мясное ассорти»', 'Бекон, пепперони, буженина, моцарелла, томатный соус', Decimal('750.00'), '550 г'),
            ('hot', 'Пицца «Пепперони Классик»', 'Пикантная салями пепперони, сыр моцарелла', Decimal('680.00'), '500 г'),
            ('hot', 'Пицца «Четыре сыра»', 'Дорблю, пармезан, чеддер, моцарелла на сливочном соусе', Decimal('690.00'), '480 г'),
            ('hot', 'Бургер «Страйк» с говядиной и картофелем фри', 'Мраморная говядина, сыр чеддер, луковые кольца', Decimal('590.00'), '420 г'),
            ('hot', 'Клаб-сэндвич с индейкой', 'Тосты, копчёная индейка, бекон, лист салата', Decimal('420.00'), '310 г'),
            ('drinks', 'Морс ягодный домашний', 'Освежающий клюквенно-брусничный морс', Decimal('190.00'), '0.5 л'),
            ('drinks', 'Лимонад «Маракуйя-Мята»', 'Свежая мята, пюре маракуйи, газированная вода', Decimal('320.00'), '0.5 л'),
            ('drinks', 'Коктейль «Мохито Классический»', 'Лайм, мята, тростниковый сахар, содовая', Decimal('380.00'), '0.4 л'),
            ('drinks', 'Коктейль «Пина Колада безалкогольная»', 'Ананасовый сок, кокосовые сливки, взбитые сливки', Decimal('390.00'), '0.35 л'),
            ('desserts', 'Чизкейк Нью-Йорк с ягодным топингом', 'Классический сырный десерт', Decimal('350.00'), '150 г'),
            ('desserts', 'Шоколадный фондан с шариком мороженого', 'Горячий кекс с жидким бельгийским шоколадом', Decimal('390.00'), '160 г'),
        ]
        menu_items = []
        for cat, title, desc, price, wv in menu_items_data:
            m, _ = MenuItem.objects.update_or_create(
                title=title,
                defaults={'category': cat, 'description': desc, 'price': price, 'weight_volume': wv, 'is_available': True}
            )
            menu_items.append(m)

        # 7. Генерация 36 реалистичных бронирований (требование: >= 30)
        self.stdout.write("Создание 36 бронирований...")
        base_date = date.today() - timedelta(days=12)

        booking_scenarios = [
            # (days_offset, start_hour, duration_hours, guests, is_bowling, num_lanes)
            # Прошедшие бронирования
            (-10, 14, 2, 4, True, 1),
            (-9, 16, 4, 10, True, 2),  # СТЫК ТАРИФОВ (16:00-20:00) + 10 гостей (2 дорожки!)
            (-9, 19, 3, 3, False, 1),
            (-8, 12, 3, 5, True, 1),
            (-8, 17, 3, 8, True, 2),  # СТЫК ТАРИФОВ (17:00-20:00) + 8 гостей (2 дорожки!)
            (-7, 18, 2, 4, False, 1),
            (-7, 20, 2, 6, True, 1),
            (-6, 15, 4, 12, True, 2), # СТЫК ТАРИФОВ (15:00-19:00) + 12 гостей (2 дорожки!)
            (-6, 21, 2, 2, False, 1),
            (-5, 13, 2, 3, True, 1),
            (-5, 17, 4, 9, True, 2),  # СТЫК ТАРИФОВ + 2 дорожки
            (-4, 16, 3, 4, True, 1),  # СТЫК ТАРИФОВ (16:00-19:00)
            (-4, 19, 2, 4, False, 1),
            (-3, 14, 3, 6, True, 1),
            (-3, 18, 3, 11, True, 2), # 11 гостей (2 дорожки!)
            (-2, 12, 2, 2, False, 1),
            (-2, 16, 4, 7, True, 2),  # СТЫК ТАРИФОВ + 7 гостей (2 дорожки!)
            (-1, 15, 2, 4, True, 1),
            (-1, 17, 4, 10, True, 2), # СТЫК ТАРИФОВ
            (-1, 20, 3, 4, False, 1),
            # Сегодняшние бронирования
            (0, 11, 2, 4, True, 1),
            (0, 14, 2, 5, True, 1),
            (0, 16, 4, 8, True, 2),   # СТЫК ТАРИФОВ + 8 гостей
            (0, 19, 3, 3, False, 1),
            (0, 20, 2, 6, True, 1),
            # Будущие бронирования
            (1, 13, 2, 4, True, 1),
            (1, 16, 4, 12, True, 2),  # СТЫК ТАРИФОВ + 12 гостей
            (1, 19, 2, 2, False, 1),
            (2, 12, 3, 6, True, 1),
            (2, 17, 3, 9, True, 2),   # СТЫК ТАРИФОВ + 9 гостей
            (2, 20, 2, 4, False, 1),
            (3, 15, 4, 10, True, 2),  # СТЫК ТАРИФОВ + 10 гостей
            (3, 18, 2, 4, True, 1),
            (4, 16, 3, 7, True, 2),   # СТЫК ТАРИФОВ + 7 гостей
            (4, 19, 3, 3, False, 1),
            (5, 14, 2, 4, True, 1),
        ]

        created_bookings_count = 0
        for i, (day_off, s_hour, dur, guests, is_bowl, lanes_cnt) in enumerate(booking_scenarios):
            b_date = base_date + timedelta(days=day_off)
            s_time = time(s_hour, 0)
            e_hour = (s_hour + dur) % 24
            e_time = time(e_hour, 0)

            client_user, client_prof = clients[i % len(clients)]
            g_type = gt_bowling if is_bowl else random.choice([gt_russian, gt_pool, gt_snooker])

            # Подбираем зоны
            if is_bowl:
                sel_zones = bowling_zones[:lanes_cnt] if lanes_cnt <= len(bowling_zones) else bowling_zones[:2]
            else:
                sel_zones = [random.choice(billiard_zones)]

            c_card = client_prof.club_card if (i % 3 != 0) else None

            pricing = calculate_booking_pricing(
                game_type=g_type,
                target_date=b_date,
                start_t=s_time,
                end_t=e_time,
                zones_count=len(sel_zones),
                club_card=c_card
            )

            # Статус
            if day_off < 0:
                b_status = 'completed'
            elif day_off == 0:
                b_status = 'confirmed'
            else:
                b_status = 'pending' if (i % 2 == 0) else 'confirmed'

            b_num = f"BK-{b_date.strftime('%y%m%d')}-{i+1:03d}"
            bk, _ = Booking.objects.update_or_create(
                booking_number=b_num,
                defaults={
                    'user': client_user,
                    'game_type': g_type,
                    'date': b_date,
                    'start_time': s_time,
                    'end_time': e_time,
                    'guests_count': guests,
                    'club_card': c_card,
                    'hours_total': pricing['total_hours'],
                    'day_hours': pricing['day_hours'],
                    'night_hours': pricing['night_hours'],
                    'game_cost': pricing['game_cost'],
                    'discount_percent': pricing['discount_percent'],
                    'discount_amount': pricing['discount_amount'],
                    'preorder_cost': Decimal('0.00'),
                    'total_cost': pricing['final_game_cost'],
                    'status': b_status,
                    'notes': 'День рождения' if guests >= 8 else 'Отдых с друзьями',
                }
            )
            bk.zones.set(sel_zones)

            # Создаем предзаказ бара для некоторых бронирований
            if i % 2 == 0 or guests > 6:
                chosen_items = random.sample(menu_items, k=random.randint(2, 4))
                for item in chosen_items:
                    qty = random.randint(1, 3)
                    PreorderItem.objects.create(
                        booking=bk,
                        menu_item=item,
                        quantity=qty,
                        price_each=item.price,
                        total_price=item.price * qty,
                        status='served' if b_status == 'completed' else 'ordered'
                    )
                bk.update_preorder_totals()

            # Платёж
            if b_status in ['confirmed', 'completed']:
                Payment.objects.update_or_create(
                    booking=bk,
                    defaults={
                        'amount': bk.total_cost,
                        'payment_method': random.choice(['card', 'sbp', 'cash']),
                        'status': 'completed',
                        'transaction_id': f"TXN-{uuid.uuid4().hex[:8].upper()}"
                    }
                )

            # Отзывы для завершенных бронирований
            if b_status == 'completed' and (i % 3 == 0):
                review_texts = [
                    "Отличные дорожки, автоматика работает идеально! Пицца мясная просто бомба.",
                    "Прекрасно провели вечер с коллегами. Очень удобно, что сразу рассчитало цену со скидкой карты.",
                    "Брали 2 дорожки на 10 человек, места хватило с запасом. Быстрая подача закусок из бара.",
                    "Столы для русского бильярда в отличном состоянии, сукно натянуто идеально. Обязательно придём снова!",
                ]
                Review.objects.update_or_create(
                    booking=bk,
                    defaults={
                        'user': client_user,
                        'rating': random.choice([5, 5, 4, 5]),
                        'comment': random.choice(review_texts)
                    }
                )

            created_bookings_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Успешно создано:\n"
            f"- Бронирований (основная таблица): {Booking.objects.count()} (требование >= 30)\n"
            f"- Игровых зон: {PlayZone.objects.count()} (требование >= 10)\n"
            f"- Клубных карт: {ClubCard.objects.count()} (требование >= 10)\n"
            f"- Позиций меню: {MenuItem.objects.count()} (требование >= 10)\n"
            f"- Пользователей: {User.objects.count()}\n"
            f"- Предзаказов бара: {PreorderItem.objects.count()}\n"
            f"- Платежей: {Payment.objects.count()}\n"
            f"- Отзывов: {Review.objects.count()}\n"
            f"Тестовые аккаунты:\n"
            f"  Администратор: admin / admin123\n"
            f"  Оператор зала: operator / operator123\n"
            f"  Менеджер бара: barman / barman123\n"
            f"  Посетитель:    ivan / client123"
        ))
