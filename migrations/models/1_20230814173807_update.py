from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `user_settings` ADD `daily_test_services` INT NOT NULL  DEFAULT 1;
        ALTER TABLE `services` ADD `is_test_service` BOOL NOT NULL  DEFAULT 0;
        CREATE TABLE `user_purchased` (
    `user_id` BIGINT NOT NULL REFERENCES `users` (`id`) ON DELETE CASCADE,
    `services_id` INT NOT NULL REFERENCES `services` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `user_purchased`;
        ALTER TABLE `user_settings` DROP COLUMN `daily_test_services`;
        ALTER TABLE `services` DROP COLUMN `is_test_service`;"""
