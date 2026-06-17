from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `rialgateway_payments` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 4,
    `provider` VARCHAR(7) NOT NULL  COMMENT 'fastpay: fastpay' DEFAULT 'fastpay',
    `data` JSON NOT NULL,
    `transaction_id` BIGINT NOT NULL UNIQUE,
    CONSTRAINT `fk_rialgate_transact_44f793a6` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        ALTER TABLE `transactions` MODIFY COLUMN `status` SMALLINT NOT NULL  COMMENT 'waiting: 1\nfailed: 2\ncanceled: 3\npartially_paid: 4\nfinished: 5\nrejected: 6' DEFAULT 1;
        ALTER TABLE `settings` ADD `fastpay_encryption_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `fastpay_api_key` VARCHAR(128);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `transactions` MODIFY COLUMN `status` SMALLINT NOT NULL  COMMENT 'waiting: 1\nfailed: 2\ncanceled: 3\npartially_paid: 4\nfinished: 5' DEFAULT 1;
        ALTER TABLE `settings` DROP COLUMN `fastpay_encryption_key`;
        ALTER TABLE `settings` DROP COLUMN `fastpay_api_key`;"""
