from typing import List
from models.game import Game

# Model for a list of games
class Games:
    def __init__(self):
        self.games: List[Game] = []
    
    def add(self, games: List[Game]):
        self.games.extend(games)
    
    def __repr__(self):
        return f"Games: {len(self.games)}"
    
    def __str__(self):
        return '\n'.join(str(game) for game in self.games)

    def __iter__(self):
        return iter(self.games)

    @property
    def count(self):
        return len(self.games)

    @property
    def discounted(self):
        return [game for game in self.games if (game.discount_percentage) > 0]
    
    def discounted_more_than(self, percentage: int):
        return [game for game in self.games if (game.discount_percentage) > percentage]

    @property
    def free(self):
        return [game for game in self.games if game.is_free and not game.free_to_play]
    
    @property
    def free_always(self):
        return [game for game in self.games if game.free_to_play]