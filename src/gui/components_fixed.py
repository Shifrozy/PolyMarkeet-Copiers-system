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
            text=market[:40] + "..." if len(market) > 40 else market,
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
