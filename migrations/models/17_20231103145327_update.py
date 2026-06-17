from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `invoice_reminders` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_invoice__users_52ece0c4` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        ALTER TABLE `settings` ADD `remind_invoices_each_n_days` INT NOT NULL  DEFAULT 3;
        ALTER TABLE `settings` ADD `disable_users_role` SMALLINT NOT NULL  COMMENT 'user: 0\nreseller: 1\nadmin: 2\nsuper_user: 3' DEFAULT 1;
        ALTER TABLE `settings` ADD `remind_invoices_after_amount` BIGINT NOT NULL  DEFAULT 1000000;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` DROP COLUMN `remind_invoices_each_n_days`;
        ALTER TABLE `settings` DROP COLUMN `disable_users_role`;
        ALTER TABLE `settings` DROP COLUMN `remind_invoices_after_amount`;
        DROP TABLE IF EXISTS `invoice_reminders`;"""
