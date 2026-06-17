from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `reserves` MODIFY COLUMN `activate_at` DATETIME(6);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `reserves` MODIFY COLUMN `activate_at` DATETIME(6) NOT NULL;"""
