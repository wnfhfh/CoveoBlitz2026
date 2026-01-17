import heapq
import math
import random
from typing import Optional
from game_message import *

spore_destinations = dict()
# Remember last positions to add hysteresis and avoid ping-pong
spore_last_positions: dict[str, Position] = {}

# Debug toggle for movement decisions
DEBUG_MOVE = True


def _dbg(*args):
    if DEBUG_MOVE:
        try:
            print(*args)
        except Exception:
            # Never let logging break the bot
            pass


def should_create_spawner(game_message: TeamGameState, my_team: TeamInfo) -> list[SporeCreateSpawnerAction]:
    """Create a spawner if we currently have none.

    Strategy (minimal to satisfy requirement):
    - If the team has zero spawners, pick the largest-biomass spore that can afford the
      current `nextSpawnerCost` and issue one `SporeCreateSpawnerAction` for it.
    - Otherwise, do nothing.
    """
    # If we already have a spawner, do nothing
    if len(my_team.spawners) > 8:
        return []

    cost = my_team.nextSpawnerCost
    
    # Define the minimum distance (radius) required between spawners
    MIN_DISTANCE = 5

    # 1. Filter: Find spores that have enough biomass AND are far enough from existing spawners
    candidates = []
    for sp in my_team.spores:
        if sp.biomass < cost:
            continue

        too_close = False
        for spawner in my_team.spawners:
            # Calculate squared Euclidean distance to avoid slow square roots
            dist_sq = (sp.position.x - spawner.position.x)**2 + (sp.position.y - spawner.position.y)**2
            
            if dist_sq < (MIN_DISTANCE ** 2):
                too_close = True
                break
        
        # Only consider this spore if it is far enough from ALL spawners
        if not too_close:
            candidates.append(sp)

    if not candidates:
        _dbg(f"should_create_spawner: no spore meets cost {cost} and distance > {MIN_DISTANCE}")
        return []

    # 2. Selection: Choose the fattest spore from the valid candidates
    candidate = max(candidates, key=lambda s: s.biomass)

    _dbg(
        f"should_create_spawner: creating spawner using spore {candidate.id} at ({candidate.position.x},{candidate.position.y}) with biomass {candidate.biomass}, cost={cost}"
    )
    return [SporeCreateSpawnerAction(sporeId=candidate.id)]


def _manhattan(a: Position, b: Position) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _owned_income(game_message: TeamGameState, my_team: TeamInfo) -> int:  # todo a utiliser
    ownership = game_message.world.ownershipGrid
    nutrients = game_message.world.map.nutrientGrid
    my_id = my_team.teamId
    h = game_message.world.map.height
    w = game_message.world.map.width
    income = 0
    for y in range(h):
        row_owner = ownership[y]
        row_nut = nutrients[y]
        for x in range(w):
            if row_owner[x] == my_id:
                income += row_nut[x]
    return income


def _in_map(x: int, y: int, game_message: TeamGameState) -> bool:
    w = game_message.world.map.width
    h = game_message.world.map.height
    return 0 <= x < w and 0 <= y < h


def find_closest_nutrients_not_ours(nutrientGrid, origin, game_message) -> list[Position]:
    # Find all positions with nutrients > 0
    nutrient_positions = []
    for r in range(len(nutrientGrid)):
        for c in range(len(nutrientGrid[0])):
            if nutrientGrid[r][c] > 0:
                nutrient_positions.append(Position(c, r))

    if not nutrient_positions:
        return []

    # Sort all nutrient positions by distance
    nutrient_positions.sort(key=lambda pos: _manhattan(pos, origin))

    filtered_positions = []

    for pos in nutrient_positions:
        owner = game_message.world.ownershipGrid[pos.y][pos.x]
        if owner != game_message.yourTeamId:
            filtered_positions.append(pos)

    return filtered_positions


def _best_target(game_message: TeamGameState, my_team: TeamInfo, origin) -> list[Position]:
    # nutrients_plus_proches = find_closest_nutrients(game_message.world.map.nutrientGrid, origin)
    meilleurs_nutrients = sorted(
        find_closest_nutrients_not_ours(game_message.world.map.nutrientGrid, origin.position, game_message),
        key=lambda pos: _path_score(game_message, my_team, origin.position, pos),
        reverse=True)  # double sort mais marche
    # meilleurs_nutrients = sort_list_list(game_message.world.map.nutrientGrid)
    return meilleurs_nutrients

def isABush(game_message: TeamGameState, position: Position) -> bool:
    avoid = False
    if (game_message.world.ownershipGrid[position.x][position.y] == "NEUTRAL"):
        avoid = True
    return avoid


def _path_score(game_message: TeamGameState, my_team: TeamInfo, start: Position, target: Position) -> int:
    """
    Simple path-based score: walk a deterministic Manhattan path (x then y).
    For every step onto a tile we don't own, add its nutrients and pay 1 biomass cost.
    Steps onto owned tiles are free and yield no immediate nutrients (already ours).
    Returns net benefit = sum(nutrients on newly-claimed tiles) - number of paid steps.
    """

    ownership = game_message.world.ownershipGrid
    # nutrients = game_message.world.map.nutrientGrid
    my_id = my_team.teamId
    at_least_one_not_owned_tile = False  # s'assurer qu'on conquerit sur le path, sinon on fait juste tourner en rond dans notre zone

    x, y = start.x, start.y
    tx, ty = target.x, target.y

    net = 0

    # Move horizontally towards target
    step_x = 1 if tx > x else -1
    while x != tx:
        x += step_x
        if not _in_map(x, y, game_message):
            break
        if ownership[y][x] != my_id:
            at_least_one_not_owned_tile = True
            # net += nutrients[y][x] * MULTIPLICATEUR_DE_VALEUR_POSITIVE  # gain
            net -= 1  # biomass cost
        # else: moving on our own trail is free and yields no new nutrients

    # Move vertically towards target
    step_y = 1 if ty > y else -1
    while y != ty:
        y += step_y
        if not _in_map(x, y, game_message):
            break
        if ownership[y][x] != my_id:
            at_least_one_not_owned_tile = True
            # net += nutrients[y][x] * MULTIPLICATEUR_DE_VALEUR_POSITIVE
            net -= 1

    return net if at_least_one_not_owned_tile else -999


def sort_list_list(nutrientGrid: list[list[int]]) -> list[tuple[int, int, int]]:
    # Create list of (value, row, col) for all cells
    values = []
    for i, row in enumerate(nutrientGrid):
        for j, val in enumerate(row):
            values.append((val, i, j))

    # Sort by value descending
    values.sort(reverse=True)

    # Return as (row, col, value)
    return [(i, j, val) for val, i, j in values]

def should_move_spore(game_message, my_team, blocked_spore_ids: Optional[set[str]] = None) -> list[SporeMoveToAction]:
    moves = list()
    targets_from_spawners = _gen_targets_from_spawners(game_message, my_team)

    our_spawners = [spawner for spawner in game_message.world.spawners if spawner.teamId == my_team.teamId]
    if our_spawners:
        for spore in my_team.spores:
            if spore.id not in spore_destinations or spore.position == spore_destinations[spore.id]:
                closest_spawner = min(our_spawners, key=lambda spawner: _manhattan(spore.position, spawner.position))
                targets = targets_from_spawners.get(closest_spawner.id) or []
                spore_destinations[spore.id] = targets[random.randint(0, len(targets)-1)]
                for position in dijkstra(game_message, spore.position, spore_destinations[spore.id]):
                    moves.append(SporeMoveToAction(spore.id, position))
            # moves.append(
            #     SporeMoveToAction(sporeId=spore.id, position=spore_destinations[spore.id])
            # )

    return moves


def should_produce_spores(game_message: TeamGameState, my_team: TeamInfo) -> list[SpawnerProduceSporeAction]:
    """Very simple production logic: produce one small spore (biomass=3) from each spawner while we have nutrients.

    This ignores threats, targets, and buffering. It only respects the one-action-per-spawner rule
    and the global nutrient constraint.
    """
    actions: list[SpawnerProduceSporeAction] = []

    remaining = my_team.nutrients
    biomass_per_spore = 10  # minimal useful size (>=2 to act, 3 gives a movement buffer)

    # shuffle the spawners to produce spores in a random order
    # (this could help avoid ping-ponging between spawners)
    spawners = list(my_team.spawners)
    random.shuffle(spawners)
    for spawner in spawners:
        if remaining / 2 < biomass_per_spore:
            break
        actions.append(SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=biomass_per_spore))
        remaining -= biomass_per_spore

    return actions


def _gen_targets_from_spawners(game_message, my_team):
    targets = dict()
    ownership = game_message.world.ownershipGrid
    my_id = game_message.yourTeamId
    our_spawners = [spawner for spawner in game_message.world.spawners if spawner.teamId == my_id]
    for spawner in our_spawners:
        # Generate targets normally, then filter out any tiles we already own,
        # same spirit as _get_best_target_not_ours
        raw_targets = _best_target(game_message, my_team, spawner) or []
        filtered = [pos for pos in raw_targets if ownership[pos.y][pos.x] != my_id]
        targets[spawner.id] = filtered
    return targets


def get_unowned_biomass_grid(game_message: TeamGameState, my_team: TeamInfo) -> list[list[int]]:
    """
    Create a grid of biomass values for cells not owned by our team.
    """
    ownership = game_message.world.ownershipGrid
    biomass = game_message.world.biomassGrid

    unowned_biomass_grid = [[0 for _ in range(game_message.world.map.width)] for _ in
                            range(game_message.world.map.height)]

    for y in range(game_message.world.map.height):
        for x in range(game_message.world.map.width):
            if ownership[y][x] != my_team.teamId:  # Check if the cell is not owned by our team
                unowned_biomass_grid[y][x] = biomass[y][x]

    return unowned_biomass_grid

def dijkstra(game_message: TeamGameState, start: Position, goal: Position) -> list[Position]:
    width = game_message.world.map.width
    height = game_message.world.map.height
    ownership = game_message.world.ownershipGrid
    my_id = game_message.yourTeamId

    n = width * height

    rStart: int = start.x * start.y
    rGoal: int = goal.x * goal.y

    def in_bounds(x, y):
        return 0 <= x < width and 0 <= y < height

    def neighbors(pos: Position):
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        for dx, dy in dirs:
            nx, ny = pos.x + dx, pos.y + dy
            if in_bounds(nx, ny):
                yield Position(nx, ny)

    def move_cost(pos: Position) -> int:
        grid = get_unowned_biomass_grid(game_message, game_message.world.teamInfos[game_message.yourTeamId])
        if (isABush(game_message, pos)):
            return grid[pos.y][pos.x]
        else:
            return 0 if ownership[pos.y][pos.x] == my_id else 1

    # Priority queue: (cost_so_far, Position)
    pq = []
    heapq.heappush(pq, (0, rStart))

    dist = [math.inf] * n
    prev = [-1] * n

    while pq:
        current_cost, current = heapq.heappop(pq)

        if current.x == goal.x and current.y == goal.y:
            break

        for nxt in neighbors(current):
            new_cost = current_cost + move_cost(nxt)
            key = (nxt.x, nxt.y)

            if key not in dist or new_cost < dist[key]:
                dist[key] = new_cost
                prev[key] = (current.x, current.y)
                heapq.heappush(pq, (new_cost, nxt))

    # Reconstruct path
    path = []
    cur_key = (goal.x, goal.y)

    if cur_key not in prev and start != goal:
        return []  # no path found

    while cur_key != (start.x, start.y):
        path.append(Position(cur_key[0], cur_key[1]))
        cur_key = prev[cur_key]

    path.append(start)
    path.reverse()

    return path


class Bot:

    def __init__(self):
        print("Initializing your super mega duper bot")

    def get_next_move(self, game_message: TeamGameState) -> list[Action]:
        """
        Strategic loop implementing spawner creation, spawner production, and spore movement.
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

        if (game_message.tick % 125) >= 100:
            return self.strat_after_x_ticks(game_message, myTeam)
        # if len(myTeam.spawners) == 0:
        #     actions.append(SporeCreateSpawnerAction(sporeId=myTeam.spores[0].id))
        # elif myTeam.nutrients > 10:
        #     actions.append(SpawnerProduceSporeAction(spawnerId=myTeam.spawners[0].id, biomass=5))
        # else:
        #     for action in self.moveAllSporesTo(myTeam.spores, self.fillSpawnerZone(myTeam.spawners[0], game_message)):
        #         actions.append(action)
        #         print(action.position.x, action.position.y)

        # Strategie Antoine
        # Record current positions to avoid immediate backtracking next tick
        for sp in myTeam.spores:
            spore_last_positions[sp.id] = sp.position


        # 1) Spawner creation decisions
        #if(game_message.tick < 100 or game_message.tick % 50 == 0):
        spawner_creations = should_create_spawner(game_message, myTeam)
        actions.extend(spawner_creations)
        blocked_spores = {a.sporeId for a in spawner_creations}

        # 2) Produce spores from spawners under budget constraints
        production = should_produce_spores(game_message, myTeam)
        actions.extend(production)

        # 4) Move spores
        spore_moves = should_move_spore(game_message, myTeam, blocked_spore_ids=blocked_spores)
        actions.extend(spore_moves)

        return actions
    
    def strat_after_x_ticks(self, game_message: TeamGameState, myTeam: TeamInfo) -> list[Action]:
        actions = []
        for spore in myTeam.spores:
            pos = spore.position
            newPos = Position(pos.x + random.randint(-3, 3), pos.y + random.randint(-3, 3))
            actions.append(
                SporeMoveToAction(sporeId=spore.id, position=newPos)
                )
        for spawner in myTeam.spawners:
            if myTeam.nutrients > 15:
                actions.append(SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=10))
        return actions
    
