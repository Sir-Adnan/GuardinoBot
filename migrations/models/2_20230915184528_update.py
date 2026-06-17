from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `settings` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `crypto_payment` BOOL NOT NULL  DEFAULT 1,
    `perfectmoney_payment` BOOL NOT NULL  DEFAULT 1,
    `rial_payment` BOOL NOT NULL  DEFAULT 1,
    `cardtocard_payment` BOOL NOT NULL  DEFAULT 1,
    `access_only` BOOL NOT NULL  DEFAULT 0,
    `referral_system` BOOL NOT NULL  DEFAULT 1,
    `minimum_pay_amount` INT NOT NULL  DEFAULT 20000,
    `default_username_prefix` VARCHAR(20) NOT NULL  DEFAULT 'Marzdemo',
    `default_daily_test_services` INT NOT NULL  DEFAULT 1,
    `payments_discount_on` INT NOT NULL  DEFAULT 400000,
    `payments_discount_on_percent` INT NOT NULL  DEFAULT 6,
    `transaction_logs` VARCHAR(30),
    `orders_logs` VARCHAR(30),
    `perfectmoney_account_id` VARCHAR(40),
    `perfectmoney_payee_account` VARCHAR(40),
    `perfectmoney_passphrase` VARCHAR(100),
    `np_api_key` VARCHAR(128)   DEFAULT '7TWKAGZ-CSF4WEM-MQSVVXW-VDRAYNA',
    `np_ipn_secret_key` VARCHAR(256)   DEFAULT '9fa66YgjqU8mlLHFRihG0jeFjg+cHbxY',
    `marzban_webhook_secret` VARCHAR(256),
    `force_join_chats` JSON
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `bot_texts` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `start` LONGTEXT NOT NULL,
    `main_menu` LONGTEXT NOT NULL,
    `force_join` LONGTEXT NOT NULL,
    `purchase` LONGTEXT NOT NULL,
    `support` LONGTEXT NOT NULL,
    `help` LONGTEXT NOT NULL,
    `command_not_found` LONGTEXT NOT NULL,
    `charge` LONGTEXT NOT NULL,
    `charge_crypto` LONGTEXT NOT NULL,
    `charge_crypto_pay` LONGTEXT NOT NULL,
    `charge_perfectmoney` LONGTEXT NOT NULL,
    `charge_perfectmoney_pay` LONGTEXT NOT NULL,
    `charge_cardtocard` LONGTEXT NOT NULL,
    `charge_cardtocard_pay` LONGTEXT NOT NULL,
    `charge_rialgateway` LONGTEXT NOT NULL,
    `charge_rialgateway_pay` LONGTEXT NOT NULL
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `settings`;
        DROP TABLE IF EXISTS `bot_texts`;"""
