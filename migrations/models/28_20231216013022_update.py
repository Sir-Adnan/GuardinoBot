from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `provider` VARCHAR(13) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping\naqayepardakht: aqayepardakht\nmadpal: madpal' DEFAULT 'fastpay';
        ALTER TABLE `settings` ADD `aqayepardakht_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی aqayepardakht';
        ALTER TABLE `settings` ADD `aqayepardakht_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `aqayepardakht_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `aqayepardakht_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `aqayepardakht_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `aqayepardakht_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `bot_texts` ADD `charge_aqayepardakht` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_aqayepardakht_pay` LONGTEXT NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `provider` VARCHAR(10) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping\nmadpal: madpal' DEFAULT 'fastpay';
        ALTER TABLE `settings` DROP COLUMN `aqayepardakht_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `aqayepardakht_free_after`;
        ALTER TABLE `settings` DROP COLUMN `aqayepardakht_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN `aqayepardakht_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `aqayepardakht_api_key`;
        ALTER TABLE `settings` DROP COLUMN `aqayepardakht_payment`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_aqayepardakht`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_aqayepardakht_pay`;"""
