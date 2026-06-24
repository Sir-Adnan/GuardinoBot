from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `servers` ADD `link_policy` VARCHAR(16) NOT NULL DEFAULT 'master_first';
        ALTER TABLE `servers` MODIFY COLUMN `username` VARCHAR(64);
        ALTER TABLE `proxies` ADD `panel_user_id` BIGINT;
        ALTER TABLE `proxies` ADD `sub_token` VARCHAR(128);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `servers` DROP COLUMN `link_policy`;
        ALTER TABLE `servers` MODIFY COLUMN `username` VARCHAR(34);
        ALTER TABLE `proxies` DROP COLUMN `panel_user_id`;
        ALTER TABLE `proxies` DROP COLUMN `sub_token`;"""
