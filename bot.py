import random
from game_message import *
import heapq


class Bot:
    def __init__(self):
        print("Initializing your super mega duper bot")

    def get_next_move(self, game_message: TeamGameState) -> list[Action]:
        """
        Here is where the magic happens, for now the moves are not very good. I bet you can do better ;)
        """
        actions = []

        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]
        if len(my_team.spawners) == 0:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[0].id))

        elif len(my_team.spores) == 0:
            actions.append(
                SpawnerProduceSporeAction(spawnerId=my_team.spawners[0].id, biomass=20)
            )

        else:
            actions.append(
                SporeMoveToAction(
                    sporeId=my_team.spores[0].id,
                    position=Position(
                        x=random.randint(0, game_message.world.map.width - 1),
                        y=random.randint(0, game_message.world.map.height - 1),
                    ),
                )
            )

        # You can clearly do better than the random actions above. Have fun!!
        return actions
    
    def action(self, game_message: TeamGameState) -> list[Action]:
        actions = []
        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]
        
        if len(my_team.spawners) == 0:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[0].id))
        elif len(my_team.spores) == 0:
            actions.append(
                SpawnerProduceSporeAction(spawnerId=my_team.spawners[0].id, biomass=20)
            )
        else:
            print(my_team.spores)
            spore = my_team.spores[0]
            best_positions = self.get_nutriments_score(game_message, spore)
            if best_positions:  # Only move if we found valid positions
                actions.append(
                    SporeMoveToAction(
                        sporeId=spore.id,
                        position=best_positions[0],  # Take the best position
                    )
                )
        return actions

    def get_nutriments_score(self, game_message: TeamGameState, spore: Spore):
        """Returns a list of Position objects sorted from best to worst score."""
        nutriments = game_message.world.map.nutrientGrid
        position_scores = []
        
        for y in range(game_message.world.map.height):
            for x in range(game_message.world.map.width):
                if nutriments[y][x] > 0:
                    position = Position(x=x, y=y)
                    score = self.score_result(game_message, position, spore, nutriments)
                    # Only include positions with valid scores
                    if score > -float('inf'):
                        position_scores.append((score, position))
        
        # Sort by score in descending order (best first)
        position_scores.sort(reverse=True, key=lambda item: item[0])
        
        # Return just the positions (without scores)
        return [position for score, position in position_scores]

    def score_result(self, game_message: TeamGameState, position: Position, spore: Spore, nutriments):
        teamId = game_message.yourTeamId
        
        # Skip tiles we already own
        if game_message.world.ownershipGrid[position.y][position.x] == teamId:
            return -float('inf')
        
        # Calculate Manhattan distance
        distance = abs(spore.position.x - position.x) + abs(spore.position.y - position.y)
        
        # Score based on nutrient value minus distance cost
        score = nutriments[position.y][position.x] * 4 - distance
        return score