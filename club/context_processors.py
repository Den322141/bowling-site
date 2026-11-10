from .models import GameType


def club_global_context(request):
    game_types = GameType.objects.all()
    user_role = 'guest'
    user_profile = None

    if request.user.is_authenticated:
        if request.user.is_superuser:
            user_role = 'admin'
        else:
            profile = getattr(request.user, 'profile', None)
            if profile:
                user_role = profile.role
                user_profile = profile
            else:
                user_role = 'visitor'

    return {
        'nav_game_types': game_types,
        'current_user_role': user_role,
        'user_profile': user_profile,
    }
