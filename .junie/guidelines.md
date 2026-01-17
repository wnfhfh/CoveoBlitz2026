
Introduction

Welcome to Ecosystem Dominance, a turn-based strategy game where you control plants and fungi competing across a grid of soil. Your goal is to eliminate all opponents or control the most tiles (soil patches) when the game ends.

You command spores (mobile units that move, fight, and claim territory) and spawners (buildings that produce new spores). The game revolves around two resources: nutrients (currency for production) and biomass (health, power, and energy for movement).

The central trade-off is the "Trail" mechanic: Spores leave biomass behind as they move, claiming territory and generating nutrients. You must balance spending biomass on movement to expand your economy against saving it for combat strength.
Playing the Game

In this competitive AI programming challenge, teams code an autonomous bot to manage their colony's expansion, economy, and combat logic.

Gameplay Overview:

    Expand: Move spores to claim tiles. Moving to new ground costs 1 biomass (leaving a trail); moving along your own trails is free.

    Harvest: Controlled tiles generate nutrients per tick based on their nutrient value.

    Produce: Spawners spend nutrients to create new spores. You determine the size as there's no biomass limit!

    Invest: Transform spores into new spawners. Be careful, costs increase exponentially: 0, 1, 3, 7, 15, 31...

To win, eliminate all opponents or control the most tiles at tick 1,000.
	
Core Mechanics

Matches last a maximum of 1,000 ticks. Each tick, your bot submits a list of actions. Every spore and spawner can execute one action per tick.

Biomass Thresholds:

• Active State: A spore needs 2+ biomass to move or fight.

• Static State: A spore with 1 biomass claims the tile but cannot act.

• Evolution: A spore with sufficient biomass can transform into a spawner.

• Unlimited Size: Spawners can create spores of any biomass amount (as long as you can afford the nutrient cost).

Movement Logic:

• Moving to an empty tile costs 1 biomass (left behind as a trail).

• Moving onto your own trail (1+ biomass) costs 0 biomass.

• A 2-biomass spore becomes static after moving to an empty tile: it leaves 1 biomass as a trail and arrives with 1 biomass, unable to move again.
Active Spores
	

Unit Capabilities:

    Move: Travel one tile (cardinal directions only). Leaves a 1 biomass trail on empty tiles.

    Secure Territory: Any tile with 1+ biomass is yours and generates nutrients per tick.

    Transform: Evolve into a spawner. Costs increase exponentially: 0, 1, 3, 7, 15, 31... biomass.

    Split: Divide a spore into two. One moves with assigned biomass; the other stays behind with the remainder.

Biomass determines power. Combat is deterministic: Stronger unit - weaker unit = winner's remaining biomass.

Friendly spores occupying the same tile combine their biomass into a single unit.

Use spores to expand territory, engage in deterministic combat, and strategically place spawners to grow your economy.
Neutral Spores
	

Neutral spores have a fixed biomass value.

Players must defeat neutral spores before they can take control of the tiles they occupy.
Resource Economy

Mastering the flow of nutrients and biomass is key to victory.

Nutrients are the currency used to produce new spores. Generate them by controlling tiles with nutrient values.

Every controlled tile yields nutrients per tick based on its specific value (typically 0 to 100+).

Biomass acts as health, power, and energy. Spores need 2+ biomass to perform actions; those with 1 biomass are static territory markers.

Movement costs 1 biomass. Spawner costs are exponential (0, 1, 3, 7, 15, 31...). Spore production costs nutrients equal to biomass amount (for example: 20 biomass costs 20 nutrients).
	
Territory & Combat

The blue spore has 3 biomass and the yellow spore has 1 in the combat, each leaving 1 behind.
	

Territory control and combat are the core competitive mechanics:

    Territory: Each tile has a nutrient value (0 to 100+). Control tiles by maintaining 1+ biomass on them.

    Combat Trigger: When enemies land on the same tile, combat resolves immediately (after movement).

    1 vs 1: The stronger unit survives. Remaining biomass = (Stronger - Weaker). Equal biomass means both units are eliminated (leaving the tile empty).

    Multi-Team: Only the two units with the most biomass fight; all others are eliminated. The winner survives with biomass equal to the difference. (Example: Three units with 50, 30, and 25 biomass → unit with 25 biomass is eliminated, 50 defeats 30, winner survives with 20 biomass).

Actions

Your chosen action must follow a specific format. You can send multiple actions per tick, but each spore and spawner can only execute one action per tick.

Invalid actions will return an error message (check `lastTickErrors`).

Action descriptions:

Move a spore one tile in the specified direction. Leaves a biomass trail on empty tiles.
	


{
  type: "SporeMove";
  sporeId: string;
  direction: Position;
}
// direction: {x:0,y:-1} (up), {x:0,y:1} (down),
//            {x:-1,y:0} (left), {x:1,y:0} (right)
  

Move a spore towards a position using pathfinding. The spore progresses one tile closer each tick along the shortest path.
	


{
  type: "SporeMoveTo";
  sporeId: string;
  position: Position;
}
  

Create a spawner using the spore's biomass at its current position. Costs increase exponentially: 0, 1, 3, 7, 15, 31...
	


{
  type: "SporeCreateSpawner";
  sporeId: string;
}
  

Create a new spore at the spawner location with specified biomass. Costs nutrients equal to biomass.
	


{
  type: "SpawnerProduceSpore";
  spawnerId: string;
  biomass: number;
}
  

Split a spore into two. The original spore moves with the specified biomass; the new spore is created at the original position with the remaining biomass.
	


{
  type: "SporeSplit";
  sporeId: string;
  biomassForMovingSpore: number;
  direction: Position;
}
// direction: {x:0,y:-1} (up), {x:0,y:1} (down),
//            {x:-1,y:0} (left), {x:1,y:0} (right)
  

Game State & Data

Every tick, your bot receives a TeamGameState object containing all game info: team data, resources, units, map details, and enemy positions.

Key Properties: nutrients (currency), spores (mobile units), spawners (buildings), nextSpawnerCost (required biomass), biomassGrid (biomass per tile), ownershipGrid (owner ID per tile), and nutrientGrid (nutrient value per tile).

Coordinates: Use Position `x=0, y=-1` (UP), `x=0, y=1` (DOWN), `x=-1, y=0` (LEFT), `x=1, y=0` (RIGHT). No diagonal movement.

Error Handling: Check lastTickErrors for feedback on invalid actions.

All game objects are fully documented in your starter kit's IDE.
Victory Conditions

Matches last a maximum of 1,000 ticks. Teams are ranked by evaluating criteria in order. First tiebreaker wins!

Elimination: You lose if you have no spawners and no actionable spores (spores with 2+ biomass). The last team standing wins.

If the game reaches tick 1,000, ranking criteria are evaluated in this order:

    Territory Controlled: Team with the most controlled tiles (1+ biomass).

    Total Resources: Combined biomass + nutrients currently held by the team.

    Spawners Built: Total lifetime spawners created (cumulative, not just current count).

    Actions Taken: Total number of actions executed throughout the match.

    Response Time: Faster bots rank higher (average response time per tick).

    Connection Order: The team that connected first to the server wins final ties.

Getting Started

Focus on uploading a working bot quickly, then iterate. Key development tips:

• Start Simple: Begin with basic expansion. Move spores to claim tiles with high nutrient values first.

• Test Locally: Use the provided tools to iterate faster before uploading to the platform.

• Cache Calculations: You have 100ms per tick. Store results from slow calculations to stay within the time limit.

• Debug with Logs: Use standard print statements; output appears in the bot logs.

• Version Control: Use Git to track changes so you can roll back if a new strategy breaks your bot.

• Check Errors: Monitor `lastTickErrors` in the game state to catch invalid actions.

• Team Coordination: Assign one person to expansion, one to combat, and one to spawner optimization.
Edge Cases

    If friendly spores move to the same tile, their biomass combines. The ID of the spore with the highest biomass is preserved.

    If multiple units move to the same tile, friendly units are merged before combat starts.

    Collision: If enemies try to move directly onto each other's current tile, the spore with lower biomass has its move canceled.