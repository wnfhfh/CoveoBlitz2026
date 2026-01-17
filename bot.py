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
        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]

        return self.strategie(game_message, my_team)

    def fillSpawnerZone(self, spawner: Spawner, game_message: TeamGameState) -> list[Position]:
        """
        Calculates the Manhattan distance between two positions.
        """
        zone_coords: list[Position] = []
        for y in range(max(0, spawner.position.y - 5), min(game_message.world.map.height, spawner.position.y + 5)):
            for x in range(max(0, spawner.position.x - 5), min(game_message.world.map.width, spawner.position.x + 5)):
                zone_coords.append(Position(x=x, y=y))
        return zone_coords

    def moveAllSporesTo(self, spores: list[Spore], targets: list[Position]) -> list[Action]:
        """
        Generates move actions for all spores to a target coordinate.
        """
        actions = []
        for spore in spores:
            actions.append(SporeMoveToAction(sporeId=spore.id, position=targets[0]))
            targets.pop(0)
            if len(targets) == 0:
                return actions
        return actions

    def isNearBy(self, position: Position, target: Position) -> bool:
        isNear = True
        if abs(position.x - target.x) > 1 or abs(position.y - target.y) > 1:
            isNear = False
        return isNear

    def numberSporeNearBy(self, spores: list[Spore], target: Position) -> int:
        count = 0
        for spore in spores:
            if self.isNearBy(spore, target):
                count += 1
        return count

    def defendCase(self, game_message: TeamGameState, defendPosition: Position, sporeId: str) -> Action:
        return SporeMoveToAction(sporeId=sporeId, position=defendPosition)
        # allTeam = game_message.world.teamInfos
        # mySpore: Spore = allTeam[game_message.yourTeamId].spores[sporeId]
        # for team in allTeam.values():
        #     if team == allTeam[game_message.yourTeamId]:
        #         pass
        #     else:
        #         for spore in team.spores:
        #             if mySpore.biomass < spore.biomass:


    def strategie(self, game_message: TeamGameState, myTeam: TeamInfo) -> list[Action]:
        actions = []

        if len(myTeam.spawners) == 0:
            actions.append(SporeCreateSpawnerAction(sporeId=myTeam.spores[0].id))
        elif myTeam.nutrients > 10:
            actions.append(SpawnerProduceSporeAction(spawnerId=myTeam.spawners[0].id, biomass=5))
        else:
            for action in self.moveAllSporesTo(myTeam.spores, self.fillSpawnerZone(myTeam.spawners[0], game_message)):
                actions.append(action)
                print(action.position.x, action.position.y)

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