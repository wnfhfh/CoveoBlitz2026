import random
from game_message import *


class Bot:

    def __init__(self):
        print("Initializing your super mega duper bot")

    def get_next_move(self, game_message: TeamGameState) -> list[Action]:
        """
        Here is where the magic happens, for now the moves are not very good. I bet you can do better ;)
        """
        actions = []

        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]

        print(f"Your team has {len(my_team.spores)} spores and {len(my_team.spawners)} spawners.")

        if len(my_team.spawners) == 0:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[0].id))
        elif my_team.nutrients > 10:
            actions.append(SpawnerProduceSporeAction(spawnerId=my_team.spawners[0].id, biomass=5))
        else:
            for action in self.moveAllSporesTo(my_team.spores, self.fillSpawnerZone(my_team.spawners[0], game_message)):
                actions.append(action)
                print(action.position.x, action.position.y)

        return actions
        # You can clearly do better than the random actions above. Have fun!!
        return actions

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