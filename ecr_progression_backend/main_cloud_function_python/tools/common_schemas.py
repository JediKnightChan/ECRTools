from marshmallow import Schema, fields, validate, EXCLUDE

ECR_FACTIONS = [
    'LoyalSpaceMarines',
    'ChaosSpaceMarines'
]

ECR_SUB_FACTIONS = [
    # LSM
    'Ultramarines',
    'BloodAngels',
    'DarkAngels',
    'ImperialFists',
    'SpaceWolves',
    'Salamanders',
    'BlackTemplars',
    'RavenGuard',
    # CSM
    'BlackLegion',
    'WordBearers',
    'NightLords',
    'IronWarriors',
    'AlphaLegion'
]


class ExcludeSchema(Schema):
    class Meta:
        unknown = EXCLUDE


class CharPlayerSchema(ExcludeSchema):
    player = fields.Int(required=True)
    char = fields.Int(required=True)
