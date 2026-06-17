from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` MODIFY COLUMN `tronseller_trx_wallet` VARCHAR(128);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` MODIFY COLUMN `tronseller_trx_wallet` VARCHAR(128) NOT NULL;"""
