from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `payments_cardtocard` ADD `admin_messages` JSON;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `payments_cardtocard` DROP COLUMN `admin_messages`;"""
