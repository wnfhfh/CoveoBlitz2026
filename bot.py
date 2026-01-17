import random
from typing import Optional
from game_message import *

DISTANCE_LIGNE_DROITE = 150
MULTIPLICATEUR_DE_VALEUR_POSITIVE = 100
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
    if len(my_team.spawners) > 0:
        return []

    cost = my_team.nextSpawnerCost

    # Choose the fattest spore that can afford the spawner cost
    candidate: Optional[Spore] = None
    for sp in my_team.spores:
        if sp.biomass >= cost and (candidate is None or sp.biomass > candidate.biomass):
            candidate = sp

    if candidate is None:
        _dbg(f"should_create_spawner: no spore can afford cost {cost}; skipping creation")
        return []

    _dbg(
        f"should_create_spawner: creating FIRST spawner using spore {candidate.id} at ({candidate.position.x},{candidate.position.y}) with biomass {candidate.biomass}, cost={cost}"
    )
    return [SporeCreateSpawnerAction(sporeId=candidate.id)]



def _manhattan(a: Position, b: Position) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _owned_income(game_message: TeamGameState, my_team: TeamInfo) -> int: #todo a utiliser
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


def _path_score(game_message: TeamGameState, my_team: TeamInfo, start: Position, target: Position) -> int:
    """
    Simple path-based score: walk a deterministic Manhattan path (x then y).
    For every step onto a tile we don't own, add its nutrients and pay 1 biomass cost.
    Steps onto owned tiles are free and yield no immediate nutrients (already ours).
    Returns net benefit = sum(nutrients on newly-claimed tiles) - number of paid steps.
    """
    ownership = game_message.world.ownershipGrid
    nutrients = game_message.world.map.nutrientGrid
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
            net += nutrients[y][x] * MULTIPLICATEUR_DE_VALEUR_POSITIVE  # gain
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
            net += nutrients[y][x] * MULTIPLICATEUR_DE_VALEUR_POSITIVE
            net -= 1

    return net if at_least_one_not_owned_tile else -999


def _best_target(game_message: TeamGameState, my_team: TeamInfo, origin) -> list[Position]:
    """Find up to top best expansion targets for a unit within search radius.

    Returns a list of Positions sorted by descending score, then ascending distance.
    If no positive targets exist, falls back to nearest non-owned tile (at most one),
    or returns an empty list if none found.
    """

    ownership = game_message.world.ownershipGrid
    my_id = my_team.teamId

    candidates: list[tuple[Position, int, int]] = []  # (pos, score, dist)

    # Primary search: collect positive-scoring targets within radius
    radius = DISTANCE_LIGNE_DROITE
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            tx = origin.position.x + dx
            ty = origin.position.y + dy

            if not _in_map(tx, ty, game_message):
                continue

            dist = abs(dx) + abs(dy)
            if dist == 0 or dist > radius:
                continue

            # Skip tiles we already own
            if ownership[ty][tx] == my_id:
                continue

            score = _path_score(game_message, my_team, origin.position, Position(tx, ty))

            # Keep only beneficial targets
            if score > 0:
                candidates.append((Position(tx, ty), score, dist))

    if candidates:
        # Sort by best score desc, then closest distance asc
        candidates.sort(key=lambda t: (-t[1], t[2]))
        top = [pos for (pos, _score, _dist) in candidates[:20]]
        first = top[0]
        _dbg(
            f"_best_target: unit {origin.id} at ({origin.position.x},{origin.position.y}) -> top {len(top)} targets, "
            f"best=({first.x},{first.y}) score={next(s for (p,s,d) in candidates if p.x==first.x and p.y==first.y)}")
        return top

    # Fallback: find nearest non-owned tile within limited radius
    _dbg(f"_best_target: no positive targets for unit {origin.id}, searching fallback")

    best_pos = _best_target_fallback(None, game_message, my_id, origin, ownership)

    return [best_pos] if best_pos is not None else []


def _best_target_fallback(best_pos, game_message, my_id, origin, ownership):
    FALLBACK_RADIUS = 20  # Limit fallback search to avoid full map scan
    best_dist = 10 ** 9
    fallback_radius = min(FALLBACK_RADIUS, max(game_message.world.map.width, game_message.world.map.height))
    for dy in range(-fallback_radius, fallback_radius + 1):
        for dx in range(-fallback_radius, fallback_radius + 1):
            tx = origin.position.x + dx
            ty = origin.position.y + dy

            if not _in_map(tx, ty, game_message):
                continue

            dist = abs(dx) + abs(dy)
            if dist == 0:
                continue

            if ownership[ty][tx] != my_id:
                if dist < best_dist:
                    best_dist = dist
                    best_pos = Position(tx, ty)
    if best_pos is not None:
        _dbg(f"_best_target: fallback found ({best_pos.x},{best_pos.y}) at distance {best_dist}")
    else:
        _dbg(f"_best_target: no targets found (map fully owned?)")
    return best_pos


def should_move_spore(game_message, my_team, blocked_spore_ids: Optional[set[str]] = None) -> list[SporeMoveToAction]:
    moves: list[SporeMoveToAction] = []

    # Ensure our destination cache uses spore ids
    global spore_destinations
    if blocked_spore_ids is None:
        blocked_spore_ids = set()

    for spore in my_team.spores:
        if not (_check_new_destination_conditions(blocked_spore_ids, moves, spore, spore_destinations)):
            continue

        # Need a new destination - pair with closest spawner
        targets_from_spawners = _gen_targets_from_spawners(game_message, my_team)
        
        our_spawners = [spawner for spawner in game_message.world.spawners if spawner.teamId == my_team.teamId]
        if our_spawners:
            closest_spawner = min(our_spawners, key=lambda spawner: _manhattan(spore.position, spawner.position))
            target_list = targets_from_spawners.get(closest_spawner.id) or []
            target = target_list[0] or None
            
            if target is None:
                # If no good target from the spawner, fallback to a per-spore best target
                _dbg(f"should_move_spore: spawner-derived target is None for spore {spore.id}; falling back to per-spore best target")
                per_spore_targets = _best_target(game_message, my_team, spore)
                target = per_spore_targets[0] if per_spore_targets else None
        else:
            # No spawners yet: use per-spore best target
            per_spore_targets = _best_target(game_message, my_team, spore)
            target = per_spore_targets[0] if per_spore_targets else None

        if target is not None and not (target.x == spore.position.x and target.y == spore.position.y):
            spore_destinations[spore.id] = target
            moves.append(SporeMoveToAction(sporeId=spore.id, position=target))
            _dbg(
                f"should_move_spore: assigning new target for spore {spore.id} at ({spore.position.x},{spore.position.y}) -> ({target.x},{target.y})")
        else:
            reason = "target is None" if target is None else "target equals current position"
            _dbg(
                # f"should_move_spore: FALLBACK random move for spore {spore.id} at ({spore.position.x},{spore.position.y}) bm={spore.biomass} because {reason}. Nearby positive targets: {near_str}")
                "FALLBACK panique panique")
            # As a last resort, try to nudge in a random cardinal direction within bounds
            dirs = [Position(1, 0), Position(-1, 0), Position(0, 1), Position(0, -1)]
            random.shuffle(dirs)
            moved = False
            for d in dirs:
                nx = spore.position.x + d.x
                ny = spore.position.y + d.y
                if _in_map(nx, ny, game_message):
                    pos = Position(nx, ny)
                    spore_destinations[spore.id] = pos
                    moves.append(SporeMoveToAction(sporeId=spore.id, position=pos))
                    _dbg(f"should_move_spore: random nudge for spore {spore.id} -> ({pos.x},{pos.y})")
                    moved = True
                    break
            if not moved:
                _dbg(
                    f"should_move_spore: random fallback could not find in-bounds direction for spore {spore.id}; clearing destination")
                spore_destinations.pop(spore.id, None)

    return moves


def _check_new_destination_conditions(blocked_spore_ids, moves, spore, spore_destinations):
    """
    Check si on doit donner une nouvelle destination au spore ce tour ci.
    conditions: biomasse > 2, cree pas de spawner ce tour ci, a deja une dest
    :return: true si doit avoir une nouvelle dest
    """
    if spore.id in blocked_spore_ids:
        # This spore will create a spawner this tick; skip issuing a move
        _dbg(
            f"_check_new_destination_conditions: spore {spore.id} at ({spore.position.x},{spore.position.y}) will create spawner; skipping move")
        spore_destinations.pop(spore.id, None)
        return False

    # Only spores with at least 2 biomass can act
    if spore.biomass < 2:
        # Clear any destination if it was set (spore may have split/changed)
        _dbg(
            f"_check_new_destination_conditions: spore {spore.id} at ({spore.position.x},{spore.position.y}) has biomass {spore.biomass} < 2; cannot act")
        spore_destinations.pop(spore.id, None)
        return False

    # Continue towards existing destination if not yet reached
    dest: Optional[Position] = spore_destinations.get(spore.id)
    if dest is not None and not (dest.x == spore.position.x and dest.y == spore.position.y):
        _dbg(
            f"_check_new_destination_conditions: spore {spore.id} continues toward existing destination ({dest.x},{dest.y}) from ({spore.position.x},{spore.position.y})")
        moves.append(SporeMoveToAction(sporeId=spore.id, position=dest))
        return False
    return True


# def _positive_targets_near(game_message: TeamGameState, my_team: TeamInfo, origin: Position, radius: int = 8,
#                            limit: int = 6) -> list[tuple[Position, int, int]]:
#     """Return up to `limit` targets around origin with positive path score.
#     Returns tuples (pos, score, dist), sorted by score desc then dist asc.
#     """
#     ownership = game_message.world.ownershipGrid
#     my_id = my_team.teamId
#
#     candidates: list[tuple[Position, int, int]] = []
#     for dy in range(-radius, radius + 1):
#         for dx in range(-radius, radius + 1):
#             x = origin.x + dx
#             y = origin.y + dy
#             if not (0 <= x < game_message.world.map.width and 0 <= y < game_message.world.map.height):
#                 continue
#             if ownership[y][x] == my_id:
#                 continue
#             dist = abs(dx) + abs(dy)
#             if dist == 0 or dist > radius:
#                 continue
#             score = _path_score(game_message, my_team, origin, Position(x, y))
#             if score > 0:
#                 candidates.append((Position(x, y), score, dist))
#
#     # sort par meilleur score, puis si meme score, par plus petite distance
#     candidates.sort(key=lambda t: (-t[1], t[2]))
#     return candidates[:limit]


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

        if len(myTeam.spawners) == 0:
            actions.append(SporeCreateSpawnerAction(sporeId=myTeam.spores[0].id))
        elif myTeam.nutrients > 10:
            actions.append(SpawnerProduceSporeAction(spawnerId=myTeam.spawners[0].id, biomass=5))
        else:
            for action in self.moveAllSporesTo(myTeam.spores, self.fillSpawnerZone(myTeam.spawners[0], game_message)):
                actions.append(action)
                print(action.position.x, action.position.y)

        return actions