from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` ADD `create_on_hold_users` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `services` ALTER COLUMN `purchaseable` SET DEFAULT 1;
        ALTER TABLE `services` ALTER COLUMN `renewable` SET DEFAULT 1;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` DROP COLUMN `create_on_hold_users`;
        ALTER TABLE `services` ALTER COLUMN `purchaseable` SET DEFAULT 0;
        ALTER TABLE `services` ALTER COLUMN `renewable` SET DEFAULT 0;"""
