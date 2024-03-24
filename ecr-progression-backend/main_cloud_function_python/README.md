
# ECR Progression backend

This is an API for interaction with ECR progression, which is basically in-game characters with 
additional data (currencies, unlocked items, unlocked cosmetics, etc.)

This could be done much cleaner, if written with something like django-rest-framework for a 
server VM with an inner database. However, our architecture is aimed for the cheapest price, so 
for data storage we use S3 and serverless database, YDB, and for API webhook we use serverless function.

YDB doesn't support ORM so raw SQL queries have to be used, S3 is also unfriendly to frameworks, 
so a lot of low-level code in the end.

## Models

### Character

Fields:
1) ID
2) Player ID
3) Name
4) Faction

Methods:
1) Get by ID
2) List all characters for a player
3) Create character (checks that no character with the same name exists, 
that player doesn't have characters with the same faction)
4) Modify character (only name can be modified)

Deleting character is not possible, sub faction can be changed any time locally in game.

Stored in YDB table `characters` or `characters-dev`

### Character Currencies Data

Fields:
1) Character ID
2) Player ID
3) XP
4) Free XP (not spent)
5) Silver
6) Gold

Methods:
1) Get currency data for character and player
2) Set currency data (not called by the game directly, only via other backend)

Stored in S3 in `{dev|prod}/{player_id}/{character_id}/currencies.json`
