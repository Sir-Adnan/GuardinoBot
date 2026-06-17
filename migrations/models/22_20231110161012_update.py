from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `provider` VARCHAR(10) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping\nmadpal: madpal' DEFAULT 'fastpay';
        ALTER TABLE `settings` ADD `madpal_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `madpal_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی madpal';
        ALTER TABLE `settings` ADD `madpal_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `madpal_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `madpal_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `madpal_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `bot_texts` ADD `charge_madpal_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_madpal` LONGTEXT NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `provider` VARCHAR(10) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping' DEFAULT 'fastpay';
        ALTER TABLE `settings` DROP COLUMN `madpal_payment`;
        ALTER TABLE `settings` DROP COLUMN `madpal_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `madpal_api_key`;
        ALTER TABLE `settings` DROP COLUMN `madpal_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `madpal_free_after`;
        ALTER TABLE `settings` DROP COLUMN `madpal_free_after_percent`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_madpal_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_madpal`;"""
