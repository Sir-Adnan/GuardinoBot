from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `byadmin_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 5;
        ALTER TABLE `cardtocard_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 2;
        ALTER TABLE `crypto_payments` MODIFY COLUMN `provider` VARCHAR(11) NOT NULL  COMMENT 'nowpayments: nowpayments\nswapwallet: swapwallet' DEFAULT 'nowpayments';
        ALTER TABLE `crypto_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 1;
        CREATE TABLE IF NOT EXISTS `eswap_payments` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 8,
    `extra_data` JSON,
    `trx_rate` INT NOT NULL,
    `transaction_id` BIGINT NOT NULL UNIQUE,
    CONSTRAINT `fk_eswap_pa_transact_08677866` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        ALTER TABLE `gift_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 6;
        ALTER TABLE `perfectmoney_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 3;
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 4;
        ALTER TABLE `transactions` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8';
        CREATE TABLE IF NOT EXISTS `tronseller_payments` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 7,
    `payment_id` CHAR(36) NOT NULL,
    `wallet` VARCHAR(128) NOT NULL,
    `tron_amount` DOUBLE NOT NULL,
    `extra_data` JSON,
    `trx_rate` INT NOT NULL,
    `transaction_id` BIGINT NOT NULL UNIQUE,
    CONSTRAINT `fk_tronsell_transact_af6ee134` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        ALTER TABLE `settings` ADD `tronseller_trx_wallet` VARCHAR(128) NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `byadmin_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 5;
        ALTER TABLE `cardtocard_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 2;
        ALTER TABLE `crypto_payments` MODIFY COLUMN `provider` VARCHAR(11) NOT NULL  COMMENT 'nowpayments: nowpayments\nswapwallet: swapwallet\ntronseller: tronseller' DEFAULT 'nowpayments';
        ALTER TABLE `crypto_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 1;
        ALTER TABLE `gift_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 6;
        ALTER TABLE `perfectmoney_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 3;
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 4;
        ALTER TABLE `transactions` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6';
        ALTER TABLE `settings` DROP COLUMN `tronseller_trx_wallet`;
        DROP TABLE IF EXISTS `eswap_payments`;
        DROP TABLE IF EXISTS `tronseller_payments`;"""
