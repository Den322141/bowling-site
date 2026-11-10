import math
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from .validators import validate_image_file


class GameType(models.Model):
    name = models.CharField("Название игры", max_length=100)
    slug = models.SlugField("Слаг", unique=True)
    description = models.TextField("Описание", blank=True)
    max_players_per_unit = models.PositiveIntegerField("Макс. игроков на 1 зону", default=6)
    is_bowling = models.BooleanField("Это боулинг (лимит 6 чел/дорожка)", default=False)
    icon = models.CharField("Иконка / эмодзи", max_length=20, default="🎳")

    class Meta:
        verbose_name = "Тип игры"
        verbose_name_plural = "Типы игр"
        ordering = ['id']

    def __str__(self):
        return f"{self.icon} {self.name}"


class PlayZone(models.Model):
    STATUS_CHOICES = (
        ('available', 'Доступна'),
        ('maintenance', 'На обслуживании / ремонт'),
    )

    game_type = models.ForeignKey(
        GameType,
        on_delete=models.CASCADE,
        related_name='zones',
        verbose_name="Тип игры"
    )
    number = models.PositiveIntegerField("Номер зоны (дорожки/стола)")
    title = models.CharField("Название", max_length=120)
    description = models.TextField("Особенности / оборудование", blank=True)
    photo = models.ImageField(
        "Фотография зоны",
        upload_to='zones/',
        blank=True,
        null=True,
        validators=[validate_image_file]
    )
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='available')
    is_vip = models.BooleanField("VIP зона", default=False)

    class Meta:
        verbose_name = "Игровая зона"
        verbose_name_plural = "Игровые зоны (дорожки и столы)"
        ordering = ['game_type', 'number']
        unique_together = ('game_type', 'number')

    def __str__(self):
        vip_mark = " (VIP)" if self.is_vip else ""
        return f"{self.title} #{self.number}{vip_mark}"


class TariffRate(models.Model):
    DAY_TYPE_CHOICES = (
        ('weekday', 'Будние дни (Пн - Чт)'),
        ('weekend', 'Выходные и праздники (Пт - Вс)'),
    )

    game_type = models.ForeignKey(
        GameType,
        on_delete=models.CASCADE,
        related_name='tariffs',
        verbose_name="Тип игры"
    )
    day_type = models.CharField("Тип дней", max_length=20, choices=DAY_TYPE_CHOICES)
    day_rate_per_hour = models.DecimalField(
        "Дневной тариф (руб/час)",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    night_rate_per_hour = models.DecimalField(
        "Вечерний тариф (руб/час)",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    day_start_hour = models.PositiveIntegerField("Начало дневного тарифа (час)", default=10)
    night_start_hour = models.PositiveIntegerField("Начало вечернего тарифа (час, стык)", default=18)
    night_end_hour = models.PositiveIntegerField("Окончание вечернего тарифа (час)", default=2)

    class Meta:
        verbose_name = "Тарифная сетка"
        verbose_name_plural = "Тарифные сетки"
        unique_together = ('game_type', 'day_type')

    def __str__(self):
        return f"{self.game_type.name} ({self.get_day_type_display()}): День {self.day_rate_per_hour}₽ / Вечер {self.night_rate_per_hour}₽"


class ClubCard(models.Model):
    card_number = models.CharField("Номер клубной карты", max_length=30, unique=True)
    card_holder_name = models.CharField("ФИО владельца", max_length=150)
    phone = models.CharField("Номер телефона", max_length=30)
    discount_percent = models.DecimalField(
        "Процент скидки",
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('50.00'))]
    )
    is_active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField("Дата выдачи", default=timezone.now)

    class Meta:
        verbose_name = "Клубная карта"
        verbose_name_plural = "Клубные карты"
        ordering = ['-created_at']

    def __str__(self):
        return f"Карта {self.card_number} ({self.card_holder_name}) — {self.discount_percent}%"


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('visitor', 'Посетитель'),
        ('operator', 'Оператор зала'),
        ('bar_manager', 'Менеджер бара'),
        ('admin', 'Администратор клуба'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="Пользователь")
    phone = models.CharField("Телефон", max_length=30, blank=True)
    avatar = models.ImageField(
        "Аватар профиля",
        upload_to='avatars/',
        blank=True,
        null=True,
        validators=[validate_image_file]
    )
    role = models.CharField("Роль в системе", max_length=20, choices=ROLE_CHOICES, default='visitor')
    club_card = models.ForeignKey(
        ClubCard,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='users',
        verbose_name="Привязанная клубная карта"
    )

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class MenuItem(models.Model):
    CATEGORY_CHOICES = (
        ('snacks', 'Снеки и закуски'),
        ('hot', 'Горячие блюда и пицца'),
        ('drinks', 'Напитки и коктейли'),
        ('desserts', 'Десерты'),
    )

    category = models.CharField("Категория", max_length=20, choices=CATEGORY_CHOICES, default='snacks')
    title = models.CharField("Название", max_length=150)
    description = models.TextField("Состав / описание", blank=True)
    price = models.DecimalField(
        "Цена (руб)",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    weight_volume = models.CharField("Выход (порция)", max_length=50, default="300 г")
    photo = models.ImageField(
        "Фото блюда",
        upload_to='menu/',
        blank=True,
        null=True,
        validators=[validate_image_file]
    )
    is_available = models.BooleanField("В наличии", default=True)

    class Meta:
        verbose_name = "Позиция меню бара"
        verbose_name_plural = "Меню бара и кухни"
        ordering = ['category', 'title']

    def __str__(self):
        return f"{self.title} — {self.price} ₽"


class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Ожидает подтверждения'),
        ('confirmed', 'Подтверждено'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменено'),
    )

    booking_number = models.CharField("Номер брони", max_length=32, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings', verbose_name="Посетитель")
    game_type = models.ForeignKey(GameType, on_delete=models.PROTECT, related_name='bookings', verbose_name="Тип игры")
    zones = models.ManyToManyField(PlayZone, related_name='bookings', verbose_name="Игровые дорожки / столы")

    date = models.DateField("Дата игры")
    start_time = models.TimeField("Время начала")
    end_time = models.TimeField("Время окончания")
    guests_count = models.PositiveIntegerField("Количество гостей", default=2, validators=[MinValueValidator(1)])

    club_card = models.ForeignKey(
        ClubCard,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='bookings',
        verbose_name="Применённая клубная карта"
    )

    hours_total = models.DecimalField("Всего часов", max_digits=4, decimal_places=2, default=Decimal('1.00'))
    day_hours = models.DecimalField("Часов в дневной тариф", max_digits=4, decimal_places=2, default=Decimal('0.00'))
    night_hours = models.DecimalField("Часов в вечерний тариф", max_digits=4, decimal_places=2, default=Decimal('0.00'))

    game_cost = models.DecimalField("Стоимость игры до скидки (руб)", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_percent = models.DecimalField("Скидка %", max_digits=5, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField("Сумма скидки (руб)", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    preorder_cost = models.DecimalField("Сумма предзаказа бара (руб)", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_cost = models.DecimalField("Итоговая сумма к оплате (руб)", max_digits=10, decimal_places=2, default=Decimal('0.00'))

    status = models.CharField("Статус бронирования", max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField("Комментарий / пожелания", blank=True)

    created_at = models.DateTimeField("Создано", default=timezone.now)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ['-date', '-start_time']

    def __str__(self):
        return f"{self.booking_number} ({self.date} {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}) - {self.user.username}"

    def update_preorder_totals(self):
        """Пересчитывает общую сумму бара и общую сумму заказа."""
        preorders = self.preorders.filter(status__in=['ordered', 'prepared', 'served'])
        total_bar = sum(item.total_price for item in preorders)
        self.preorder_cost = Decimal(str(total_bar))
        self.total_cost = (self.game_cost - self.discount_amount) + self.preorder_cost
        self.save(update_fields=['preorder_cost', 'total_cost'])


class PreorderItem(models.Model):
    STATUS_CHOICES = (
        ('ordered', 'Заказано'),
        ('prepared', 'Готовится'),
        ('served', 'Подано к дорожке'),
        ('cancelled', 'Отменено'),
    )

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='preorders', verbose_name="Бронирование")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name='preorder_items', verbose_name="Блюдо / напиток")
    quantity = models.PositiveIntegerField("Количество", default=1, validators=[MinValueValidator(1)])
    price_each = models.DecimalField("Цена за единицу (руб)", max_digits=8, decimal_places=2)
    total_price = models.DecimalField("Общая стоимость (руб)", max_digits=10, decimal_places=2)
    status = models.CharField("Статус позиции", max_length=20, choices=STATUS_CHOICES, default='ordered')

    class Meta:
        verbose_name = "Позиция предзаказа"
        verbose_name_plural = "Позиции предзаказа бара"
        ordering = ['id']

    def save(self, *args, **kwargs):
        if not self.price_each:
            self.price_each = self.menu_item.price
        self.total_price = self.price_each * Decimal(str(self.quantity))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.menu_item.title} x {self.quantity} шт."


class Payment(models.Model):
    METHOD_CHOICES = (
        ('card', 'Банковская карта онлайн'),
        ('cash', 'Наличными при визите'),
        ('sbp', 'Система быстрых платежей (СБП)'),
    )
    STATUS_CHOICES = (
        ('completed', 'Оплачено'),
        ('pending', 'Ожидает оплаты'),
        ('refunded', 'Возврат средств'),
    )

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments', verbose_name="Бронирование")
    amount = models.DecimalField("Сумма (руб)", max_digits=10, decimal_places=2)
    payment_method = models.CharField("Способ оплаты", max_length=20, choices=METHOD_CHOICES, default='card')
    status = models.CharField("Статус платежа", max_length=20, choices=STATUS_CHOICES, default='completed')
    transaction_id = models.CharField("Номер транзакции", max_length=64, blank=True)
    created_at = models.DateTimeField("Время платежа", default=timezone.now)

    class Meta:
        verbose_name = "Оплата"
        verbose_name_plural = "Оплаты"
        ordering = ['-created_at']

    def __str__(self):
        return f"Платёж #{self.id} на {self.amount}₽ ({self.get_status_display()})"


class Review(models.Model):
    booking = models.OneToOneField(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='review',
        verbose_name="Бронирование"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', verbose_name="Автор")
    rating = models.PositiveSmallIntegerField(
        "Оценка (1-5)",
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField("Отзыв об отдыхе в клубе")
    created_at = models.DateTimeField("Дата отзыва", default=timezone.now)

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы клиентов"
        ordering = ['-created_at']

    def __str__(self):
        return f"Отзыв от {self.user.username} (оценка: {self.rating}/5)"
