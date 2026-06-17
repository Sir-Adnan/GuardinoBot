from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` ADD `usage_reset_strategy` VARCHAR(8) NOT NULL  COMMENT 'no_reset: no_reset\nday: day\nweek: week\nmonth: month\nyear: year' DEFAULT 'no_reset';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` DROP COLUMN `usage_reset_strategy`;"""
