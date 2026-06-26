from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` ADD `button_icon` VARCHAR(64);
        ALTER TABLE `services` ADD `button_style` VARCHAR(16);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` DROP COLUMN `button_icon`;
        ALTER TABLE `services` DROP COLUMN `button_style`;"""
