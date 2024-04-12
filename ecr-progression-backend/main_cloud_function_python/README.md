
# ECR Progression backend

This is an API for interaction with ECR progression, which is basically in-game characters with 
additional data (currencies, unlocked items, unlocked cosmetics, etc.)

This could be done much cleaner, if written with something like django-rest-framework for a 
server VM with an inner database. However, our architecture is aimed for the cheapest price, so 
for data storage we use S3 and serverless database, YDB, and for API webhook we use serverless function.

YDB doesn't support ORM so raw SQL queries have to be used, S3 is also unfriendly to frameworks, 
so a lot of low-level code in the end.

## Resources

### Player

Model fields:
1) ID
2) Level
3) XP
4) Free XP
5) Silver
6) Gold

Methods:
1) Get by ID (will create new player if not present and asking player is asking about himself)

Stored in YDB table `players` or `players-dev`

### Character

Model fields:
1) ID
2) Player ID
3) Name
4) Faction
5) Guild
6) Guild Role
7) Campaign Progress

Methods:
1) Get by ID
2) List all characters for a player
3) Create character (checks that no character with the same name exists, 
that player doesn't have characters with the same faction)
4) Modify character (only name can be modified)

Deleting character is not possible, sub faction can be changed any time locally in game.

Stored in YDB table `characters` or `characters-dev`

### Cosmetic Store

Methods:
1) Get all unlocked cosmetics for a character
2) Unlock a cosmetic item, spending currency

Stored in S3 in `{dev|prod}/{player_id}/{character_id}/unlocked_cosmetics.json`

### Listen Server

Methods:
1) Get all data about character: base player data (see Player) and unlocked cosmetics (see Cosmetic Store)

Combines data from Player and Unlocked Cosmetics for one request
