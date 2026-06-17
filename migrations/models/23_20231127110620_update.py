from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` ADD `username_generator` VARCHAR(11) NOT NULL  COMMENT 'randomized: randomized\nincremental: incremental' DEFAULT 'randomized';
        ALTER TABLE `proxies` MODIFY COLUMN `status` VARCHAR(12) NOT NULL  COMMENT 'active: active\ndisabled: disabled\nlimited: limited\nexpired: expired\non_hold: on_hold' DEFAULT 'active';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` DROP COLUMN `username_generator`;
        ALTER TABLE `proxies` MODIFY COLUMN `status` VARCHAR(12) NOT NULL  COMMENT 'active: active\ndisabled: disabled\nlimited: limited\nexpired: expired' DEFAULT 'active';"""
