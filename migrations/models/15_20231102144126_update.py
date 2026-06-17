from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` ADD IF NOT EXISTS `cardtocard_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `swapwallet_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `np_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `perfectmoney_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `swapwallet_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `np_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `cardtocard_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `fastpay_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `fastpay_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `tronseller_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `tronseller_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `payping_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `payping_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD IF NOT EXISTS `perfectmoney_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `payments_discount_on`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `payments_discount_on_percent`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `minimum_pay_amount`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_crypto`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_cardtocard`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_perfectmoney`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_rialgateway`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_cardtocard_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_perfectmoney_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_select_rial_provider`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_crypto_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_rialgateway_pay`;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` ADD IF NOT EXISTS `payments_discount_on` INT NOT NULL  DEFAULT 400000;
        ALTER TABLE `settings` ADD IF NOT EXISTS `payments_discount_on_percent` INT NOT NULL  DEFAULT 6;
        ALTER TABLE `settings` ADD IF NOT EXISTS `minimum_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `cardtocard_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `swapwallet_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `np_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `perfectmoney_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `swapwallet_free_after`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `np_free_after`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `cardtocard_free_after`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `fastpay_free_after`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `fastpay_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `tronseller_free_after`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `tronseller_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `payping_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `payping_free_after`;
        ALTER TABLE `settings` DROP COLUMN IF EXISTS `perfectmoney_free_after`;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_crypto` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_cardtocard` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_perfectmoney` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_rialgateway` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_cardtocard_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_perfectmoney_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_select_rial_provider` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_crypto_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_rialgateway_pay` LONGTEXT NOT NULL;"""
