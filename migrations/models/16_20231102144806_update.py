from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_tronseller_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_fastpay_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_swapwallet_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_payping` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_fastpay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_payping_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_crypto` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_swapwallet` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_cardtocard` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_perfectmoney` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_crypto_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_cardtocard_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD IF NOT EXISTS `charge_tronseller` LONGTEXT NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_tronseller_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_fastpay_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_swapwallet_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_payping`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_fastpay`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_payping_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_crypto`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_swapwallet`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_cardtocard`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_perfectmoney`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_crypto_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_cardtocard_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN IF EXISTS `charge_tronseller`;"""
