from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `provider` VARCHAR(10) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping' DEFAULT 'fastpay';
        ALTER TABLE `settings` ADD `payping_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `payping_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `swapwallet_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی swapwallet';
        ALTER TABLE `settings` ADD `fastpay_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی fastpay';
        ALTER TABLE `settings` ADD `swapwallet_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `fastpay_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `swapwallet_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `payping_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی payping';
        ALTER TABLE `settings` DROP COLUMN `rial_payment`;
        ALTER TABLE `bot_texts` ADD `charge_select_rial_provider` LONGTEXT NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `provider` VARCHAR(7) NOT NULL  COMMENT 'fastpay: fastpay' DEFAULT 'fastpay';
        ALTER TABLE `settings` ADD `rial_payment` BOOL NOT NULL  DEFAULT 1;
        ALTER TABLE `settings` DROP COLUMN `payping_payment`;
        ALTER TABLE `settings` DROP COLUMN `payping_api_key`;
        ALTER TABLE `settings` DROP COLUMN `swapwallet_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `fastpay_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `swapwallet_payment`;
        ALTER TABLE `settings` DROP COLUMN `fastpay_payment`;
        ALTER TABLE `settings` DROP COLUMN `swapwallet_api_key`;
        ALTER TABLE `settings` DROP COLUMN `payping_menu_title`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_select_rial_provider`;"""
