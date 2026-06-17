from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `crypto_payments` ADD `provider` VARCHAR(11) NOT NULL  COMMENT 'nowpayments: nowpayments\nswapwallet: swapwallet\ntronseller: tronseller' DEFAULT 'nowpayments';
        ALTER TABLE `crypto_payments` ADD `extra_data` JSON;
        ALTER TABLE `rialgateway_payments` DROP COLUMN `usdt_rate`;
        ALTER TABLE `settings` ADD `cardtocard_menu_title` VARCHAR(50) NOT NULL  DEFAULT '💳 کارت به کارت';
        ALTER TABLE `settings` ADD `np_menu_title` VARCHAR(50) NOT NULL  DEFAULT '💸 ارز دیجیتال';
        ALTER TABLE `settings` ADD `tronseller_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `payping_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `tronseller_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `tronseller_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی tronseller';
        ALTER TABLE `settings` ADD `np_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `cardtocard_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `tronseller_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `fastpay_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `swapwallet_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `perfectmoney_menu_title` VARCHAR(50) NOT NULL  DEFAULT '💵 ووچر پرفکت‌مانی';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `crypto_payments` DROP COLUMN `provider`;
        ALTER TABLE `crypto_payments` DROP COLUMN `extra_data`;
        ALTER TABLE `rialgateway_payments` ADD `usdt_rate` INT NOT NULL;
        ALTER TABLE `settings` DROP COLUMN `cardtocard_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `np_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_payment`;
        ALTER TABLE `settings` DROP COLUMN `payping_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `np_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `cardtocard_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_api_key`;
        ALTER TABLE `settings` DROP COLUMN `fastpay_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `swapwallet_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `perfectmoney_menu_title`;"""
