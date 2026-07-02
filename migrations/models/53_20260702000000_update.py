from tortoise import BaseDBAsyncClient


# User.Role gained `support = 2` between reseller(1) and admin(2→3),
# super_user moved 3→4. Shift existing rows up in one statement (each row is
# evaluated against its pre-update value, so no ordering hazard).
async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE `users` SET `role` = `role` + 1 WHERE `role` >= 2;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE `users` SET `role` = `role` - 1 WHERE `role` >= 3;"""
