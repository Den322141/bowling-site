from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ICONS = {
    'bowling': '''<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <circle cx="9" cy="9" r="1.5" fill="currentColor"></circle>
        <circle cx="15" cy="9" r="1.5" fill="currentColor"></circle>
        <circle cx="12" cy="14" r="1.5" fill="currentColor"></circle>
    </svg>''',
    
    'billiards': '''<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <path d="M12 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"></path>
        <path d="M12 11a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"></path>
    </svg>''',

    'pool': '''<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="5" width="20" height="14" rx="3"></rect>
        <circle cx="6" cy="9" r="1.2" fill="currentColor"></circle>
        <circle cx="18" cy="9" r="1.2" fill="currentColor"></circle>
        <circle cx="6" cy="15" r="1.2" fill="currentColor"></circle>
        <circle cx="18" cy="15" r="1.2" fill="currentColor"></circle>
        <circle cx="12" cy="12" r="2.5"></circle>
    </svg>''',

    'snooker': '''<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="16" rx="2"></rect>
        <path d="M3 10h18"></path>
        <circle cx="12" cy="15" r="2" fill="currentColor"></circle>
    </svg>''',

    'cocktail': '''<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M8 22h8"></path>
        <path d="M12 15v7"></path>
        <path d="m3 3 9 9 9-9z"></path>
    </svg>''',

    'pizza': '''<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="m12 2 10 18a12 12 0 0 1-20 0z"></path>
        <circle cx="12" cy="12" r="1.5" fill="currentColor"></circle>
        <circle cx="10" cy="16" r="1.5" fill="currentColor"></circle>
        <circle cx="15" cy="15" r="1.5" fill="currentColor"></circle>
    </svg>''',

    'user': '''<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
        <circle cx="12" cy="7" r="4"></circle>
    </svg>''',

    'calendar': '''<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
        <line x1="16" y1="2" x2="16" y2="6"></line>
        <line x1="8" y1="2" x2="8" y2="6"></line>
        <line x1="3" y1="10" x2="21" y2="10"></line>
    </svg>''',

    'clock': '''<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <polyline points="12 6 12 12 16 14"></polyline>
    </svg>''',

    'card': '''<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="5" width="20" height="14" rx="2"></rect>
        <line x1="2" y1="10" x2="22" y2="10"></line>
    </svg>''',

    'receipt': '''<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1-2 1z"></path>
        <line x1="8" y1="8" x2="16" y2="8"></line>
        <line x1="8" y1="12" x2="16" y2="12"></line>
        <line x1="8" y1="16" x2="12" y2="16"></line>
    </svg>''',

    'chart': '''<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="20" x2="18" y2="10"></line>
        <line x1="12" y1="20" x2="12" y2="4"></line>
        <line x1="6" y1="20" x2="6" y2="14"></line>
    </svg>''',

    'users': '''<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
        <circle cx="9" cy="7" r="4"></circle>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
        <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
    </svg>'''
}


@register.simple_tag
def icon(name, css_class=""):
    svg = ICONS.get(name, '')
    if css_class and svg:
        svg = svg.replace('<svg ', f'<svg class="{css_class}" ')
    return mark_safe(svg)
