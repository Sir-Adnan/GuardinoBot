from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `service_menues` ADD `button_icon` VARCHAR(64);
        ALTER TABLE `service_menues` ADD `button_style` VARCHAR(16);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `service_menues` DROP COLUMN `button_icon`;
        ALTER TABLE `service_menues` DROP COLUMN `button_style`;"""
