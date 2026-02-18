"""
Theme Configuration
==================
Modern dark theme configuration for the dashboard.
"""

# Color Palette - Premium Dark Theme
COLORS = {
    # Primary Colors
    "bg_dark": "#0D1117",           # Main background
    "bg_secondary": "#161B22",      # Card background
    "bg_tertiary": "#21262D",       # Elevated elements
    
    # Accent Colors
    "accent_primary": "#58A6FF",    # Primary blue
    "accent_secondary": "#1F6FEB",  # Darker blue
    "accent_gradient_start": "#667EEA",
    "accent_gradient_end": "#764BA2",
    
    # Status Colors
    "success": "#3FB950",           # Green for profit/success
    "success_light": "#2EA043",
    "danger": "#F85149",            # Red for loss/error
    "danger_light": "#DA3633",
    "warning": "#D29922",           # Yellow for warnings
    "info": "#58A6FF",              # Blue for info
    
    # Text Colors
    "text_primary": "#F0F6FC",      # Primary text
    "text_secondary": "#8B949E",    # Secondary text
    "text_muted": "#6E7681",        # Muted text
    
    # Border Colors
    "border": "#30363D",            # Standard border
    "border_light": "#21262D",      # Light border
    
    # Chart Colors
    "chart_green": "#00D26A",
    "chart_red": "#FF6B6B",
    "chart_blue": "#4DABF7",
    "chart_purple": "#9775FA",
    "chart_orange": "#FF922B",
    "chart_cyan": "#22B8CF",
}

# Font Configuration
FONTS = {
    "heading_large": ("Inter", 28, "bold"),
    "heading": ("Inter", 20, "bold"),
    "subheading": ("Inter", 16, "bold"),
    "body": ("Inter", 14),
    "body_bold": ("Inter", 14, "bold"),
    "small": ("Inter", 12),
    "tiny": ("Inter", 10),
    "mono": ("JetBrains Mono", 12),
    "mono_small": ("JetBrains Mono", 10),
}

# Spacing
SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 16,
    "lg": 24,
    "xl": 32,
    "xxl": 48,
}

# Border Radius
RADIUS = {
    "sm": 4,
    "md": 8,
    "lg": 12,
    "xl": 16,
    "round": 9999,
}


def get_pnl_color(value: float) -> str:
    """Get color based on P&L value."""
    if value > 0:
        return COLORS["success"]
    elif value < 0:
        return COLORS["danger"]
    return COLORS["text_secondary"]


def format_pnl(value: float, include_sign: bool = True) -> str:
    """Format P&L value with sign and color indicator."""
    if include_sign:
        sign = "+" if value > 0 else ""
        return f"{sign}${value:,.2f}"
    return f"${abs(value):,.2f}"


def format_percentage(value: float) -> str:
    """Format percentage value."""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"
