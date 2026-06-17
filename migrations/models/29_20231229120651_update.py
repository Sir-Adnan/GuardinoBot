from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` ALTER COLUMN `max_post_paid_credit` SET DEFAULT 1000000;
        DELETE FROM `discounts`;
        ALTER TABLE `discounts` ADD `use_counts` INT;
        ALTER TABLE `discounts` ADD `used_times` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `discounts` ADD `on_purchase` BOOL NOT NULL  DEFAULT 1;
        ALTER TABLE `discounts` ADD `code` VARCHAR(32)  UNIQUE;
        ALTER TABLE `discounts` ADD `once_per_user` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `discounts` ADD `on_renew` BOOL NOT NULL  DEFAULT 0;
        CREATE TABLE `user_discounts` (
    `user_id` BIGINT NOT NULL REFERENCES `users` (`id`) ON DELETE CASCADE,
    `discounts_id` INT NOT NULL REFERENCES `discounts` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        CREATE TABLE `user_reserved_discount` (
    `user_id` BIGINT NOT NULL REFERENCES `users` (`id`) ON DELETE CASCADE,
    `discounts_id` INT NOT NULL REFERENCES `discounts` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        ALTER TABLE `discounts` ADD UNIQUE INDEX `uid_discounts_code_8162c0` (`code`);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `user_discounts`;
        DROP TABLE IF EXISTS `user_reserved_discount`;
        ALTER TABLE `users` ALTER COLUMN `max_post_paid_credit` SET DEFAULT 5000000;
        ALTER TABLE `discounts` DROP COLUMN `use_counts`;
        ALTER TABLE `discounts` DROP COLUMN `used_times`;
        ALTER TABLE `discounts` DROP COLUMN `on_purchase`;
        ALTER TABLE `discounts` DROP COLUMN `code`;
        ALTER TABLE `discounts` DROP COLUMN `once_per_user`;
        ALTER TABLE `discounts` DROP COLUMN `on_renew`;"""
