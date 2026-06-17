from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `rialgateway_payments` ADD `usdt_rate` INT NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `rialgateway_payments` DROP COLUMN `usdt_rate`;"""
