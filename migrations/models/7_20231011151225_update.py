from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` ADD `show_test_service_in_menu` BOOL NOT NULL  DEFAULT 1;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` DROP COLUMN `show_test_service_in_menu`;"""
