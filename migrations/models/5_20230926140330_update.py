from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` ADD `show_connect_links_button` BOOL NOT NULL  DEFAULT 1;
        ALTER TABLE `settings` ADD `reset_password_button` BOOL NOT NULL  DEFAULT 1;
        ALTER TABLE `settings` ADD `card_to_card_random_amount` BOOL NOT NULL  DEFAULT 1;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` DROP COLUMN `show_connect_links_button`;
        ALTER TABLE `settings` DROP COLUMN `reset_password_button`;
        ALTER TABLE `settings` DROP COLUMN `card_to_card_random_amount`;"""
