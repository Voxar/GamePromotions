from models.game import Game

# Model for a list of games
class Games:
    def __init__(self):
        self.games = [Game]
    
    def add(self, games: [Game]):
        self.games.extend(games)
    
    def __repr__(self):
        return f"Games: {len(self.games)}"
    
    def __str__(self):
        return '\n'.join(str(game) for game in self.games)

    def __iter__(self):
        return iter(self.games)

    @property
    def discounted(self):
        return [game for game in self.games if game.discount_percentage > 0]

    @property
    def free(self):
        return [game for game in self.games if game.price == 0]