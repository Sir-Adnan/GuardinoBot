from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` ADD `user_filter` BOOL NOT NULL  DEFAULT 0;
        CREATE TABLE `services_users_filters` (
    `user_id` BIGINT NOT NULL REFERENCES `users` (`id`) ON DELETE CASCADE,
    `services_id` INT NOT NULL REFERENCES `services` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `services_users_filters`;
        ALTER TABLE `services` DROP COLUMN `user_filter`;"""
