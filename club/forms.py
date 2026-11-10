from datetime import date, time, timedelta
from decimal import Decimal
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import (
    Booking, PlayZone, GameType, ClubCard,
    UserProfile, MenuItem, PreorderItem, Review
)
from .services import validate_bowling_capacity, get_conflicting_zones, calculate_booking_pricing


class UserRegisterForm(forms.ModelForm):
    first_name = forms.CharField(label="Ваше имя", max_length=50, required=True)
    phone = forms.CharField(label="Номер телефона", max_length=30, required=True)
    email = forms.EmailField(label="Электронная почта", required=True)
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput, min_length=6)
    password_confirm = forms.CharField(label="Повторите пароль", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'email']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Пользователь с таким логином уже зарегистрирован.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Введённые пароли не совпадают.")
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Имя", max_length=50, required=False)
    email = forms.EmailField(label="Электронная почта", required=False)

    class Meta:
        model = UserProfile
        fields = ['phone', 'avatar']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=commit)
        user = profile.user
        user.first_name = self.cleaned_data.get('first_name', user.first_name)
        user.email = self.cleaned_data.get('email', user.email)
        user.save()
        return profile


class ClubCardApplyForm(forms.Form):
    card_number = forms.CharField(
        label="Номер клубной карты",
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Например, CLUB-1001'})
    )
    phone = forms.CharField(
        label="Телефон, на который оформлена карта",
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': '+7 (999) 000-00-00'})
    )

    def clean(self):
        cleaned_data = super().clean()
        card_num = cleaned_data.get('card_number')
        phone = cleaned_data.get('phone')

        if card_num and phone:
            card = ClubCard.objects.filter(card_number__iexact=card_num.strip(), is_active=True).first()
            if not card:
                raise ValidationError("Клубная карта с таким номером не найдена или неактивна.")
            cleaned_data['card'] = card
        return cleaned_data


TIME_CHOICES = [
    (time(h, 0), f"{h:02d}:00") for h in [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 0, 1]
]


class BookingForm(forms.ModelForm):
    zones = forms.ModelMultipleChoiceField(
        queryset=PlayZone.objects.filter(status='available'),
        widget=forms.CheckboxSelectMultiple,
        label="Выберите дорожки / столы"
    )
    club_card_code = forms.CharField(
        label="Номер клубной карты (при наличии)",
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'CLUB-XXXX'})
    )

    class Meta:
        model = Booking
        fields = ['game_type', 'date', 'start_time', 'end_time', 'guests_count', 'zones', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.Select(choices=TIME_CHOICES),
            'end_time': forms.Select(choices=TIME_CHOICES),
            'guests_count': forms.NumberInput(attrs={'min': 1, 'max': 30}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Особые пожелания или имена гостей'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Автоматически подставляем клубную карту пользователя, если есть
        if self.user and hasattr(self.user, 'profile') and self.user.profile.club_card:
            self.fields['club_card_code'].initial = self.user.profile.club_card.card_number

        if self.instance and self.instance.pk:
            self.fields['zones'].initial = self.instance.zones.all()

    def clean(self):
        cleaned_data = super().clean()
        game_type = cleaned_data.get('game_type')
        target_date = cleaned_data.get('date')
        start_t = cleaned_data.get('start_time')
        end_t = cleaned_data.get('end_time')
        guests_count = cleaned_data.get('guests_count') or 1
        zones = cleaned_data.get('zones')
        card_code = cleaned_data.get('club_card_code')

        if target_date and target_date < date.today():
            self.add_error('date', "Нельзя забронировать на прошедшую дату.")

        if start_t and end_t:
            s_min = start_t.hour * 60 + start_t.minute
            e_min = end_t.hour * 60 + end_t.minute
            if e_min <= s_min:
                e_min += 24 * 60
            duration_minutes = e_min - s_min
            if duration_minutes < 60:
                self.add_error('end_time', "Минимальное время бронирования — 1 час.")

        # Проверка соответствия выбранных зон типу игры
        if game_type and zones:
            for zone in zones:
                if zone.game_type != game_type:
                    self.add_error('zones', f"Зона «{zone.title}» не относится к выбранному типу игры ({game_type.name}).")

        # Особое требование Варианта 4: максимум 6 человек на одну дорожку боулинга
        if game_type and zones:
            try:
                validate_bowling_capacity(game_type, guests_count, len(zones))
            except ValidationError as e:
                self.add_error('zones', e.message)

        # Проверка пересечений по времени
        if target_date and start_t and end_t and zones:
            zone_ids = [z.id for z in zones]
            exclude_id = self.instance.pk if self.instance and self.instance.pk else None
            conflicting = get_conflicting_zones(zone_ids, target_date, start_t, end_t, exclude_booking_id=exclude_id)
            if conflicting:
                conflict_names = [z.title for z in zones if z.id in conflicting]
                self.add_error(
                    'zones',
                    f"Следующие зоны уже забронированы на это время: {', '.join(conflict_names)}. Выберите другое время или другие дорожки."
                )

        # Проверка клубной карты
        if card_code and card_code.strip():
            card = ClubCard.objects.filter(card_number__iexact=card_code.strip(), is_active=True).first()
            if not card:
                self.add_error('club_card_code', "Указанная клубная карта не найдена или заблокирована.")
            else:
                cleaned_data['verified_card'] = card
        else:
            cleaned_data['verified_card'] = None

        return cleaned_data


class PreorderAddForm(forms.ModelForm):
    class Meta:
        model = PreorderItem
        fields = ['menu_item', 'quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={'min': 1, 'max': 50, 'class': 'form-input-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['menu_item'].queryset = MenuItem.objects.filter(is_available=True)


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(choices=[(i, f"{i} {'★' * i}") for i in range(5, 0, -1)]),
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Поделитесь вашими впечатлениями о дорожках, кухне и атмосфере'}),
        }
