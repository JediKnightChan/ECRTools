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
    id = fields.UUID(required=True)
    player_id = fields.Str(
        required=True,
        validate=validate.Regexp(
            regex=r'^[a-zA-Z0-9\s]+$',
            error='String must contain only English characters, spaces, and numbers.'
        )
    )
