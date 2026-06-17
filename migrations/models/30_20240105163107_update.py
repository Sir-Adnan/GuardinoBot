from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP PROCEDURE IF EXISTS DeleteIndexRandomAm;
        CREATE PROCEDURE DeleteIndexRandomAm()
        BEGIN

            IF EXISTS ( SELECT * FROM INFORMATION_SCHEMA.STATISTICS  WHERE TABLE_NAME = 'cardtocard_payments'
                AND INDEX_NAME = 'random_amount') THEN
                    ALTER TABLE  cardtocard_payments DROP index random_amount;
            END IF;
        END;
        ALTER TABLE `cardtocard_payments` DROP IF EXISTS `random_amount`;
        ALTER TABLE `byadmin_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7' DEFAULT 5;
        ALTER TABLE `cardtocard_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7' DEFAULT 2;
        ALTER TABLE `crypto_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7' DEFAULT 1;
        ALTER TABLE `crypto_payments` MODIFY COLUMN `provider` VARCHAR(11) NOT NULL  COMMENT 'nowpayments: nowpayments\nswapwallet: swapwallet\neswap: eswap\nswapino: swapino' DEFAULT 'nowpayments';
        ALTER TABLE `gift_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7' DEFAULT 6;
        ALTER TABLE `perfectmoney_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7' DEFAULT 3;
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7' DEFAULT 4;
        ALTER TABLE `transactions` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7';
        ALTER TABLE `tronseller_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7' DEFAULT 7;
        ALTER TABLE `settings` DROP COLUMN `fastpay_api_key`;
        ALTER TABLE `settings` DROP COLUMN `fastpay_payment`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `madpal_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `madpal_payment`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_api_key`;
        ALTER TABLE `settings` DROP COLUMN `fastpay_free_after`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_free_after`;
        ALTER TABLE `settings` DROP COLUMN `madpal_api_key`;
        ALTER TABLE `settings` DROP COLUMN `fastpay_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN `fastpay_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `madpal_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN `swapwallet_free_after`;
        ALTER TABLE `settings` DROP COLUMN `madpal_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `fastpay_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `swapwallet_payment`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_trx_wallet`;
        ALTER TABLE `settings` DROP COLUMN `fastpay_encryption_key`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN `swapwallet_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `madpal_free_after`;
        ALTER TABLE `settings` DROP COLUMN `swapwallet_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `card_to_card_random_amount`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_payment`;
        ALTER TABLE `settings` DROP COLUMN `swapwallet_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN `swapwallet_api_key`;
        ALTER TABLE `settings` DROP COLUMN `tronseller_min_pay_amount`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_madpal_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_madpal`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_fastpay`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_swapwallet_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_fastpay_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_swapwallet`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_tronseller_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_tronseller`;
        ALTER TABLE `settings` ADD `swapino_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `eswap_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی eswap';
        ALTER TABLE `settings` ADD `eswap_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `swapino_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `swapino_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `eswap_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `swapino_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی swapino';
        ALTER TABLE `settings` ADD `swapino_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `eswap_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `swapino_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `eswap_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `eswap_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `bot_texts` ADD `charge_swapino_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_eswap` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_swapino` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_eswap_pay` LONGTEXT NOT NULL;
        DROP TABLE IF EXISTS `eswap_payments`;
        
        DROP PROCEDURE IF EXISTS DeleteIndexRandomAm;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `cardtocard_payments` ADD `random_amount` INT;
        UPDATE `cardtocard_payments` SET `random_amount` = ((SELECT transactions.amount FROM `transactions` WHERE `transactions`.`id` = `cardtocard_payments`.`transaction_id`) * 10 + FLOOR( 1 + RAND( ) *10000 ));
        ALTER TABLE `cardtocard_payments` MODIFY COLUMN `random_amount` INT NOT NULL UNIQUE;
        DROP PROCEDURE IF EXISTS AddIndexRandomAm;
        CREATE PROCEDURE AddIndexRandomAm()
        BEGIN

            IF NOT EXISTS ( SELECT * FROM INFORMATION_SCHEMA.STATISTICS  WHERE TABLE_NAME = 'cardtocard_payments'
                AND INDEX_NAME = 'random_amount') THEN
                    ALTER TABLE `cardtocard_payments` ADD CONSTRAINT PRIMARY KEY `idx_cardtocard__random__91bac8` (`random_amount`);
            END IF;
        END;

        ALTER TABLE `byadmin_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 5;
        ALTER TABLE `cardtocard_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 2;
        ALTER TABLE `crypto_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 1;
        ALTER TABLE `crypto_payments` MODIFY COLUMN `provider` VARCHAR(11) NOT NULL  COMMENT 'nowpayments: nowpayments\nswapwallet: swapwallet' DEFAULT 'nowpayments';
        ALTER TABLE `gift_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 6;
        ALTER TABLE `perfectmoney_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 3;
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 4;
        ALTER TABLE `transactions` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8';
        ALTER TABLE `tronseller_payments` MODIFY COLUMN `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6\ntronseller: 7\neswap: 8' DEFAULT 7;
        ALTER TABLE `settings` DROP COLUMN `swapino_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `eswap_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `eswap_min_pay_amount`;
        ALTER TABLE `settings` DROP COLUMN `swapino_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN `swapino_payment`;
        ALTER TABLE `settings` DROP COLUMN `eswap_free_after_percent`;
        ALTER TABLE `settings` DROP COLUMN `swapino_menu_title`;
        ALTER TABLE `settings` DROP COLUMN `swapino_free_after`;
        ALTER TABLE `settings` DROP COLUMN `eswap_payment`;
        ALTER TABLE `settings` DROP COLUMN `swapino_api_key`;
        ALTER TABLE `settings` DROP COLUMN `eswap_api_key`;
        ALTER TABLE `settings` DROP COLUMN `eswap_free_after`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_swapino_pay`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_eswap`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_swapino`;
        ALTER TABLE `bot_texts` DROP COLUMN `charge_eswap_pay`;
        ALTER TABLE `settings` ADD `fastpay_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `fastpay_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `tronseller_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی tronseller';
        ALTER TABLE `settings` ADD `madpal_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی madpal';
        ALTER TABLE `settings` ADD `madpal_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `tronseller_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `fastpay_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `tronseller_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `madpal_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `fastpay_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `fastpay_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `madpal_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `swapwallet_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `madpal_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `fastpay_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی fastpay';
        ALTER TABLE `settings` ADD `swapwallet_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `tronseller_trx_wallet` VARCHAR(128);
        ALTER TABLE `settings` ADD `fastpay_encryption_key` VARCHAR(256);
        ALTER TABLE `settings` ADD `tronseller_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `swapwallet_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `settings` ADD `madpal_free_after` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `swapwallet_menu_title` VARCHAR(50) NOT NULL  DEFAULT 'درگاه ریالی swapwallet';
        ALTER TABLE `settings` ADD `card_to_card_random_amount` BOOL NOT NULL  DEFAULT 1;
        ALTER TABLE `settings` ADD `tronseller_payment` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `swapwallet_free_after_percent` INT NOT NULL  DEFAULT 0;
        ALTER TABLE `settings` ADD `swapwallet_api_key` VARCHAR(128);
        ALTER TABLE `settings` ADD `tronseller_min_pay_amount` INT NOT NULL  DEFAULT 20000;
        ALTER TABLE `bot_texts` ADD `charge_madpal_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_madpal` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_fastpay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_swapwallet_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_fastpay_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_swapwallet` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_tronseller_pay` LONGTEXT NOT NULL;
        ALTER TABLE `bot_texts` ADD `charge_tronseller` LONGTEXT NOT NULL;
        
        DROP PROCEDURE IF EXISTS AddIndexRandomAm;
        """
