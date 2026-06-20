from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `servers` ADD `panel_type` VARCHAR(16) NOT NULL DEFAULT 'marzban';
        ALTER TABLE `services` ADD `panel_config` JSON;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `servers` DROP COLUMN `panel_type`;
        ALTER TABLE `services` DROP COLUMN `panel_config`;"""
