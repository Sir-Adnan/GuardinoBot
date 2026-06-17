from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `byadmin_payments` RENAME TO `payments_byadmin`;
        ALTER TABLE `cardtocard_payments` RENAME TO `payments_cardtocard`;
        ALTER TABLE `crypto_payments` RENAME TO `payments_crypto`;
        ALTER TABLE `gift_payments` RENAME TO `payments_gift`;
        ALTER TABLE `perfectmoney_payments` RENAME TO `payments_perfectmoney`;
        ALTER TABLE `rialgateway_payments` RENAME TO `payments_rialgateway`;
        ALTER TABLE `transactions` RENAME TO `payment_transactions`;
        ALTER TABLE `tronseller_payments` RENAME TO `payments_tronseller`;
        ALTER TABLE `payments_tronseller` ADD `unique_code` VARCHAR(128);
        ALTER TABLE `payments_tronseller` ADD `provider` VARCHAR(10) NOT NULL  COMMENT 'tronseller: tronseller\ntronado: tronado' DEFAULT 'tronseller';
        ALTER TABLE `payments_tronseller` DROP COLUMN `payment_id`;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `payments_byadmin` RENAME TO `byadmin_payments`;
        ALTER TABLE `payments_cardtocard` RENAME TO `cardtocard_payments`;
        ALTER TABLE `payments_crypto` RENAME TO `crypto_payments`;
        ALTER TABLE `payments_gift` RENAME TO `gift_payments`;
        ALTER TABLE `payments_perfectmoney` RENAME TO `perfectmoney_payments`;
        ALTER TABLE `payments_rialgateway` RENAME TO `rialgateway_payments`;
        ALTER TABLE `payment_transactions` RENAME TO `transactions`;
        ALTER TABLE `payments_tronseller` RENAME TO `tronseller_payments`;
        ALTER TABLE `payments_tronseller` ADD `payment_id` CHAR(36) NOT NULL;
        ALTER TABLE `payments_tronseller` DROP COLUMN `unique_code`;
        ALTER TABLE `payments_tronseller` DROP COLUMN `provider`;"""
