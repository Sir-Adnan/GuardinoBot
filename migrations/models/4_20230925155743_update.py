from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `user_settings` ADD `proxy_list_filter_by` VARCHAR(20)   COMMENT 'all: all\nactive: active\ndisabled: disabled\nlimited: limited\nexpired: expired';
        ALTER TABLE `settings` ALTER COLUMN `default_username_prefix` SET DEFAULT 'Marzdemo';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `user_settings` DROP COLUMN `proxy_list_filter_by`;
        ALTER TABLE `settings` ALTER COLUMN `default_username_prefix` SET DEFAULT 'SpeedPrBot';"""
