
# Model for a single game
class Game:
    def __init__(self):
        self.title = ""
        self.description = ""
        self.url = ""
        self._original_price = ""
        self._discount_price = ""
        self._discount_percentage = ""
        self.valid_until = ""
        self.source = ""
        self.image_url = ""
        self._posted = False  # Track if this game has been posted
        self.currency = ""
        self.free_to_play = False

    def _parse_price(self, price_str):
        if not price_str:
            return 0.0
        # Remove all non-numeric characters except decimal point
        try:
            return float(''.join(c for c in str(price_str) if c.isdigit() or c == '.'))
        except (ValueError, TypeError):
            return 0.0
            
    @property
    def is_free(self):
        return self.price == 0

    @property
    def is_discounted(self):
        return self.price < self.original_price
    
    @property
    def price(self):
        return self._parse_price(self._discount_price or self._original_price)

    @property
    def original_price(self):
        return self._parse_price(self._original_price)

    @property
    def discount_percentage(self):
        if self.original_price == 0:
            return 0
        return float(self._discount_percentage or (self.price / self.original_price) * 100)

    @property
    def id(self):
        return self.url
    
    def __repr__(self):
        return f"Game: '{self.title}'"
    
    def __str__(self) -> str:
        """Return a nicely formatted string representation of the game."""
        lines = []
        lines.append(f"{self.title}")

        # Add source and URL if available
        if hasattr(self, 'source') and self.source:
            lines.append(f"  Source: {self.source.title()}")
        
        lines.append(f"  {self.description[:100]}..." if self.description else "")

        if self.free_to_play:
            lines.append(f"  Price: Free to play")
        else:
            lines.append(f"  Price: {self.price} {self.currency}")
        
            if hasattr(self, 'discount_price') and self.discount_price:
                lines.append(f"  New Price: {self.discount_price} {self.currency}")

            if hasattr(self, 'discount_percentage') and self.discount_percentage > 0:
                lines.append(f"  Discount: {self.discount_percentage}% off")

        # Add valid until information if available
        if hasattr(self, 'valid_until') and self.valid_until:
            lines.append(f"  Offer ends: {self.valid_until}")

        if hasattr(self, 'url') and self.url:
            lines.append(f"  Url: {self.url}")

        if hasattr(self, 'image_url') and self.image_url:
            lines.append(f"  Image: {self.image_url}")
            
        return '\n'.join(line for line in lines if line)
