"""
Reusable UI Components
=====================
Custom widgets for the dashboard.
"""

import customtkinter as ctk
from typing import Optional, Callable, List, Tuple
from datetime import datetime

from .theme import COLORS, FONTS, SPACING, RADIUS, get_pnl_color, format_pnl, format_percentage


class GlassCard(ctk.CTkFrame):
    """A glass-morphism style card container."""
    
    def __init__(
        self,
        parent,
        title: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=RADIUS["lg"],
            **kwargs
        )
        
        self.configure(border_width=1, border_color=COLORS["border"])
        
        if title:
            self.title_label = ctk.CTkLabel(
                self,
                text=title,
                font=FONTS["subheading"],
                text_color=COLORS["text_primary"]
            )
            self.title_label.pack(
                anchor="w",
                padx=SPACING["md"],
                pady=(SPACING["md"], SPACING["xs"])
            )
            
            # Separator line
            separator = ctk.CTkFrame(
                self,
                height=1,
                fg_color=COLORS["border"]
            )
            separator.pack(fill="x", padx=SPACING["md"])


class StatCard(ctk.CTkFrame):
    """A card displaying a single statistic with label and value."""
    
    def __init__(
        self,
        parent,
        label: str,
        value: str = "0",
        subtitle: Optional[str] = None,
        icon: Optional[str] = None,
        value_color: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=RADIUS["lg"],
            **kwargs
        )
        
        self.configure(border_width=1, border_color=COLORS["border"])
        
        # Inner padding frame
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=SPACING["md"], pady=SPACING["sm"])
        
        # Icon and label row
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x")
        
        if icon:
            icon_label = ctk.CTkLabel(
                header,
                text=icon,
                font=("Segoe UI Emoji", 16),
                text_color=COLORS["text_secondary"]
            )
            icon_label.pack(side="left", padx=(0, SPACING["sm"]))
        
        label_widget = ctk.CTkLabel(
            header,
            text=label.upper(),
            font=FONTS["tiny"],
            text_color=COLORS["text_muted"]
        )
        label_widget.pack(side="left")
        
        # Value
        self.value_label = ctk.CTkLabel(
            inner,
            text=value,
            font=FONTS["subheading"],
            text_color=value_color or COLORS["text_primary"]
        )
        self.value_label.pack(anchor="w", pady=(2, 0))
        
        # Subtitle
        if subtitle:
            self.subtitle_label = ctk.CTkLabel(
                inner,
                text=subtitle,
                font=FONTS["small"],
                text_color=COLORS["text_secondary"]
            )
            self.subtitle_label.pack(anchor="w")
    
    def update_value(self, value: str, color: Optional[str] = None):
        """Update the displayed value."""
        self.value_label.configure(text=value)
        if color:
            self.value_label.configure(text_color=color)


class TradeHistoryTable(ctk.CTkScrollableFrame):
    """A scrollable table for displaying trade history."""
    
    COLUMNS = ["Time", "Market", "Side", "Size", "Price", "Status"]
    
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=RADIUS["lg"],
            **kwargs
        )
        
        self._rows: List[ctk.CTkFrame] = []
        
        # Header
        self._create_header()
    
    def _create_header(self):
        """Create table header."""
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_tertiary"], corner_radius=RADIUS["sm"])
        header.pack(fill="x", pady=(0, SPACING["sm"]))
        
        for i, col in enumerate(self.COLUMNS):
            label = ctk.CTkLabel(
                header,
                text=col,
                font=FONTS["small"],
                text_color=COLORS["text_muted"],
                width=100
            )
            label.pack(side="left", padx=SPACING["sm"], pady=SPACING["sm"])
    
    def add_trade(
        self,
        time: str,
        market: str,
        side: str,
        size: str,
        price: str,
        status: str
    ):
        """Add a trade row to the table."""
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=2)
        
        # Alternate row colors
        if len(self._rows) % 2 == 0:
            row.configure(fg_color=COLORS["bg_tertiary"])
        
        data = [time, market, side, size, price, status]
        colors = [
            COLORS["text_secondary"],
            COLORS["text_primary"],
            COLORS["success"] if side == "BUY" else COLORS["danger"],
            COLORS["text_primary"],
            COLORS["text_primary"],
            COLORS["success"] if status == "Filled" else COLORS["warning"]
        ]
        
        for text, color in zip(data, colors):
            label = ctk.CTkLabel(
                row,
                text=text[:20] if len(text) > 20 else text,
                font=FONTS["small"],
                text_color=color,
                width=100,
                anchor="w"
            )
            label.pack(side="left", padx=SPACING["sm"], pady=SPACING["sm"])
        
        self._rows.append(row)
        
        # Keep only last 50 rows
        if len(self._rows) > 50:
            old_row = self._rows.pop(0)
            old_row.destroy()
    
    def clear(self):
        """Clear all rows."""
        for row in self._rows:
            row.destroy()
        self._rows.clear()


class StatusIndicator(ctk.CTkFrame):
    """A pulsing status indicator."""
    
    def __init__(
        self,
        parent,
        label: str = "Status",
        status: str = "Offline",
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        # Indicator dot
        self.indicator = ctk.CTkFrame(
            self,
            width=12,
            height=12,
            corner_radius=6,
            fg_color=COLORS["text_muted"]
        )
        self.indicator.pack(side="left", padx=(0, SPACING["sm"]))
        self.indicator.pack_propagate(False)
        
        # Label
        self.label = ctk.CTkLabel(
            self,
            text=f"{label}: {status}",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"]
        )
        self.label.pack(side="left")
        
        self._status = status
    
    def set_status(self, status: str, online: bool = False):
        """Update status."""
        self._status = status
        color = COLORS["success"] if online else COLORS["text_muted"]
        self.indicator.configure(fg_color=color)
        self.label.configure(text=f"Status: {status}")


class ActionButton(ctk.CTkButton):
    """A styled action button."""
    
    def __init__(
        self,
        parent,
        text: str,
        variant: str = "primary",
        icon: Optional[str] = None,
        **kwargs
    ):
        # Determine colors based on variant
        if variant == "primary":
            fg_color = COLORS["accent_primary"]
            hover_color = COLORS["accent_secondary"]
            text_color = COLORS["bg_dark"]
        elif variant == "success":
            fg_color = COLORS["success"]
            hover_color = COLORS["success_light"]
            text_color = COLORS["bg_dark"]
        elif variant == "danger":
            fg_color = COLORS["danger"]
            hover_color = COLORS["danger_light"]
            text_color = COLORS["text_primary"]
        else:  # secondary
            fg_color = COLORS["bg_tertiary"]
            hover_color = COLORS["border"]
            text_color = COLORS["text_primary"]
        
        display_text = f"{icon} {text}" if icon else text
        
        super().__init__(
            parent,
            text=display_text,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            font=FONTS["body_bold"],
            corner_radius=RADIUS["md"],
            height=40,
            **kwargs
        )


class PnLDisplay(ctk.CTkFrame):
    """A large P&L display with percentage."""
    
    def __init__(self, parent, label: str = "Total P&L", **kwargs):
        super().__init__(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=RADIUS["lg"],
            **kwargs
        )
        
        self.configure(border_width=1, border_color=COLORS["border"])
        
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=SPACING["md"], pady=SPACING["sm"])
        
        # Label
        ctk.CTkLabel(
            inner,
            text=label.upper(),
            font=FONTS["small"],
            text_color=COLORS["text_muted"]
        ).pack(anchor="w")
        
        # Value row
        value_row = ctk.CTkFrame(inner, fg_color="transparent")
        value_row.pack(fill="x", pady=(SPACING["sm"], 0))
        
        # Main value
        self.value_label = ctk.CTkLabel(
            value_row,
            text="$0.00",
            font=FONTS["heading_large"],
            text_color=COLORS["text_primary"]
        )
        self.value_label.pack(side="left")
        
        # Percentage badge
        self.pct_label = ctk.CTkLabel(
            value_row,
            text="0.00%",
            font=FONTS["body_bold"],
            text_color=COLORS["text_secondary"],
            fg_color=COLORS["bg_tertiary"],
            corner_radius=RADIUS["sm"],
            padx=8,
            pady=4
        )
        self.pct_label.pack(side="left", padx=(SPACING["md"], 0))
    
    def update(self, value: float, percentage: float):
        """Update the P&L display."""
        color = get_pnl_color(value)
        
        self.value_label.configure(
            text=format_pnl(value),
            text_color=color
        )
        self.pct_label.configure(
            text=format_percentage(percentage),
            text_color=color,
            fg_color=COLORS["bg_tertiary"]
        )


class PositionRow(ctk.CTkFrame):
    """A row displaying a single position."""
    
    def __init__(
        self,
        parent,
        market: str,
        outcome: str,
        size: float,
        avg_price: float,
        current_price: float,
        pnl: float,
        **kwargs
    ):
        super().__init__(
            parent,
            fg_color=COLORS["bg_tertiary"],
            corner_radius=RADIUS["md"],
            **kwargs
        )
        
        self._avg_price = avg_price
        
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", padx=SPACING["md"], pady=SPACING["sm"])
        
        # Left side - Market info
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(
            left,
            text=market[:65] + "..." if len(market) > 65 else market,
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            left,
            text=f"{outcome} • Size: {size:.2f} • Avg: ${avg_price:.3f}",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w")
        
        # Right side - P&L
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")
        
        pnl_color = get_pnl_color(pnl)
        self.pnl_label = ctk.CTkLabel(
            right,
            text=format_pnl(pnl),
            font=FONTS["body_bold"],
            text_color=pnl_color
        )
        self.pnl_label.pack(anchor="e")
        
        price_change = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
        self.price_label = ctk.CTkLabel(
            right,
            text=f"${current_price:.3f} ({format_percentage(price_change)})",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"]
        )
        self.price_label.pack(anchor="e")

    def update_data(self, current_price: float, pnl: float):
        """Update the position data."""
        pnl_color = get_pnl_color(pnl)
        self.pnl_label.configure(
            text=format_pnl(pnl),
            text_color=pnl_color
        )
        
        # Update price and change
        price_change = ((current_price - self._avg_price) / self._avg_price * 100) if self._avg_price > 0 else 0
        self.price_label.configure(
            text=f"${current_price:.3f} ({format_percentage(price_change)})"
        )


class TerminalConsole(ctk.CTkFrame):
    """A terminal-like console for system logs."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color="#0D0F14",  # Deep terminal black
            corner_radius=RADIUS["md"],
            border_width=1,
            border_color=COLORS["border"],
            **kwargs
        )
        
        # Text area
        self.text_area = ctk.CTkTextbox(
            self,
            fg_color="transparent",
            text_color="#A9B1D6",  # Tokyo Night-ish light gray
            font=("Consolas", 12),
            wrap="word",
            padx=10,
            pady=10
        )
        self.text_area.pack(fill="both", expand=True)
        self.text_area.configure(state="disabled")
        
        # Max lines to keep
        self._max_lines = 500
        self._current_lines = 0
    
    def log(self, message: str, level: str = "INFO"):
        """Add a log message to the terminal."""
        self.text_area.configure(state="normal")
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color prefix based on level
        prefixes = {
            "INFO": " [INFO]  ",
            "SUCCESS": " [OK]    ",
            "WARNING": " [WARN]  ",
            "ERROR": " [ERR]   ",
            "CRITICAL": " [CRIT]  "
        }
        
        prefix = prefixes.get(level, f" [{level}] ")
        full_msg = f"{timestamp}{prefix}{message}\n"
        
        self.text_area.insert("end", full_msg)
        
        # Auto-scroll
        self.text_area.see("end")
        self.text_area.configure(state="disabled")
        
        self._current_lines += 1
        if self._current_lines > self._max_lines:
            self.clear_half()

    def clear_half(self):
        """Clear first half of logs to save memory."""
        self.text_area.configure(state="normal")
        self.text_area.delete("1.0", f"{self._max_lines // 2}.0")
        self._current_lines = self._max_lines // 2
        self.text_area.configure(state="disabled")

    def clear(self):
        """Clear all logs."""
        self.text_area.configure(state="normal")
        self.text_area.delete("1.0", "end")
        self._current_lines = 0
        self.text_area.configure(state="disabled")
