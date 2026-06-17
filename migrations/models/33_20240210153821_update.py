from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `service_menues` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `title` VARCHAR(64) NOT NULL UNIQUE,
    `description` LONGTEXT,
    `purchase` BOOL NOT NULL  DEFAULT 1,
    `renew` BOOL NOT NULL  DEFAULT 0,
    `resellers_only` BOOL NOT NULL  DEFAULT 0,
    `users_only` BOOL NOT NULL  DEFAULT 0,
    `parent_id` INT,
    CONSTRAINT `fk_service__service__6806f5db` FOREIGN KEY (`parent_id`) REFERENCES `service_menues` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;

        CREATE TABLE `user_to_service_menues` (
    `user_id` BIGINT NOT NULL REFERENCES `users` (`id`) ON DELETE CASCADE,
    `service_menues_id` INT NOT NULL REFERENCES `service_menues` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;

        CREATE TABLE `services_to_menues` (
    `service_id` INT NOT NULL REFERENCES `services` (`id`) ON DELETE CASCADE,
    `service_menues_id` INT NOT NULL REFERENCES `service_menues` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;


        ALTER TABLE `bot_texts` RENAME TO `bot_texts_old`;

        CREATE TABLE IF NOT EXISTS `bot_settings` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `_key` VARCHAR(128) NOT NULL  PRIMARY KEY,
    `_value` LONGTEXT
) CHARACTER SET utf8mb4;


        CREATE TABLE IF NOT EXISTS `bot_texts` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `_key` VARCHAR(128) NOT NULL  PRIMARY KEY,
    `_value` LONGTEXT
) CHARACTER SET utf8mb4;


        INSERT IGNORE INTO bot_settings (_key, _value)
    SELECT * FROM
(
    SELECT 'username_generator', (SELECT username_generator FROM `settings` LIMIT 1)
UNION ALL SELECT 'access_only', (SELECT access_only FROM `settings` LIMIT 1)
UNION ALL SELECT 'referral_system', (SELECT referral_system FROM `settings` LIMIT 1)
UNION ALL SELECT 'reset_password_button', (SELECT reset_password_button FROM `settings` LIMIT 1)
UNION ALL SELECT 'show_connect_links_button', (SELECT show_connect_links_button FROM `settings` LIMIT 1)
UNION ALL SELECT 'show_test_service_in_menu', (SELECT show_test_service_in_menu FROM `settings` LIMIT 1)
UNION ALL SELECT 'disable_users_role', (SELECT disable_users_role FROM `settings` LIMIT 1)
UNION ALL SELECT 'remind_invoices_each_n_days', (SELECT remind_invoices_each_n_days FROM `settings` LIMIT 1)
UNION ALL SELECT 'remind_invoices_after_amount', (SELECT remind_invoices_after_amount FROM `settings` LIMIT 1)
UNION ALL SELECT 'charge_amount_list', (SELECT charge_amount_list FROM `settings` LIMIT 1)
UNION ALL SELECT 'charge_amount_orders', (SELECT charge_amount_orders FROM `settings` LIMIT 1)
UNION ALL SELECT 'default_username_prefix', (SELECT default_username_prefix FROM `settings` LIMIT 1)
UNION ALL SELECT 'default_daily_test_services', (SELECT default_daily_test_services FROM `settings` LIMIT 1)
UNION ALL SELECT 'transaction_logs', (SELECT transaction_logs FROM `settings` LIMIT 1)
UNION ALL SELECT 'orders_logs', (SELECT orders_logs FROM `settings` LIMIT 1)
UNION ALL SELECT 'referral_discount_percent', (SELECT referral_discount_percent FROM `settings` LIMIT 1)
UNION ALL SELECT 'cancel_payback_fee', (SELECT cancel_payback_fee FROM `settings` LIMIT 1)
UNION ALL SELECT 'cancel_payback_days', (SELECT cancel_payback_days FROM `settings` LIMIT 1)

UNION ALL SELECT 'payment_nowpayments', (SELECT JSON_OBJECT('enabled', crypto_payment, 'api_key', np_api_key, 'ipn_secret_key', np_ipn_secret_key, 'min_pay_amount', np_min_pay_amount, 'menu_title', np_menu_title, 'free_after', np_free_after, 'free_after_percent', np_free_after_percent) FROM `settings` LIMIT 1)
UNION ALL SELECT 'payment_eswap', (SELECT JSON_OBJECT('enabled', eswap_payment, 'api_key', eswap_api_key, 'min_pay_amount', eswap_min_pay_amount, 'menu_title', eswap_menu_title, 'free_after', eswap_free_after, 'free_after_percent', eswap_free_after_percent) FROM `settings` LIMIT 1)
UNION ALL SELECT 'payment_swapino', (SELECT JSON_OBJECT('enabled', swapino_payment, 'min_pay_amount', swapino_min_pay_amount, 'menu_title', swapino_menu_title, 'free_after', swapino_free_after, 'free_after_percent', swapino_free_after_percent) FROM `settings` LIMIT 1)

UNION ALL SELECT 'payment_card_to_card', (SELECT JSON_OBJECT('enabled', cardtocard_payment, 'min_pay_amount', cardtocard_min_pay_amount, 'menu_title', cardtocard_menu_title, 'free_after', cardtocard_free_after, 'free_after_percent', cardtocard_free_after_percent) FROM `settings` LIMIT 1)
UNION ALL SELECT 'payment_perfect_money', (SELECT JSON_OBJECT('enabled', perfectmoney_payment, 'account_id', perfectmoney_account_id, 'payee_account', perfectmoney_payee_account, 'passphrase', 'perfectmoney_passphrase', 'menu_title', perfectmoney_menu_title, 'free_after', perfectmoney_free_after, 'free_after_percent', perfectmoney_free_after_percent) FROM `settings` LIMIT 1)

UNION ALL SELECT 'payment_payping', (SELECT JSON_OBJECT('enabled', payping_payment, 'api_key', payping_api_key, 'min_pay_amount', payping_min_pay_amount, 'menu_title', payping_menu_title, 'free_after', payping_free_after, 'free_after_percent', payping_free_after_percent) FROM `settings` LIMIT 1)
UNION ALL SELECT 'payment_aqaye_pardakht', (SELECT JSON_OBJECT('enabled', aqayepardakht_payment, 'api_key', aqayepardakht_api_key, 'min_pay_amount', aqayepardakht_min_pay_amount, 'menu_title', aqayepardakht_menu_title, 'free_after', aqayepardakht_free_after, 'free_after_percent', aqayepardakht_free_after_percent) FROM `settings` LIMIT 1)

UNION ALL SELECT 'marzban_webhook_secret', (SELECT marzban_webhook_secret FROM `settings` LIMIT 1)
UNION ALL SELECT 'force_join_chats', (SELECT force_join_chats FROM `settings` LIMIT 1)
) as `temp_settings`
    WHERE EXISTS (SELECT 1 from `settings`);


        INSERT IGNORE INTO bot_texts (_key, _value)
    SELECT * FROM
(
    SELECT 'start', (SELECT JSON_OBJECT('value', start) FROM `bot_texts_old` LIMIT 1)
UNION ALL SELECT 'main_menu', (SELECT JSON_OBJECT('value', main_menu) FROM `bot_texts_old` LIMIT 1)
UNION ALL SELECT 'force_join', (SELECT JSON_OBJECT('value', force_join) FROM `bot_texts_old` LIMIT 1)
UNION ALL SELECT 'purchase', (SELECT JSON_OBJECT('value', purchase) FROM `bot_texts_old` LIMIT 1)
UNION ALL SELECT 'support', (SELECT JSON_OBJECT('value', support) FROM `bot_texts_old` LIMIT 1)
UNION ALL SELECT 'help', (SELECT JSON_OBJECT('value', help) FROM `bot_texts_old` LIMIT 1)
UNION ALL SELECT 'proxy_help', (SELECT JSON_OBJECT('value', show_proxy_help) FROM `bot_texts_old` LIMIT 1)
UNION ALL SELECT 'referral_banner_text', (SELECT JSON_OBJECT('value', referral_banner_text) FROM `bot_texts_old` LIMIT 1)
UNION ALL SELECT 'charge', (SELECT JSON_OBJECT('value', charge) FROM `bot_texts_old` LIMIT 1)
UNION ALL SELECT 'command_not_found', (SELECT JSON_OBJECT('value', command_not_found) FROM `bot_texts_old` LIMIT 1)

UNION ALL SELECT 'payment_nowpayments', (SELECT JSON_OBJECT('choose_amount', (SELECT JSON_OBJECT('value', t.charge_crypto)), 'show_invoice', (SELECT JSON_OBJECT('value', t.charge_crypto_pay))) FROM `bot_texts_old` as t LIMIT 1)
UNION ALL SELECT 'payment_eswap', (SELECT JSON_OBJECT('choose_amount', (SELECT JSON_OBJECT('value', t.charge_eswap)), 'show_invoice', (SELECT JSON_OBJECT('value', t.charge_eswap_pay))) FROM `bot_texts_old` as t LIMIT 1)
UNION ALL SELECT 'payment_swapino', (SELECT JSON_OBJECT('choose_amount', (SELECT JSON_OBJECT('value', t.charge_swapino)), 'show_invoice', (SELECT JSON_OBJECT('value', t.charge_swapino_pay))) FROM `bot_texts_old` as t LIMIT 1)

UNION ALL SELECT 'payment_card_to_card', (SELECT JSON_OBJECT('choose_amount', (SELECT JSON_OBJECT('value', t.charge_cardtocard)), 'show_invoice', (SELECT JSON_OBJECT('value', t.charge_cardtocard_pay))) FROM `bot_texts_old` as t LIMIT 1)
UNION ALL SELECT 'payment_perfect_money', (SELECT JSON_OBJECT('show_info', (SELECT JSON_OBJECT('value', t.charge_perfectmoney))) FROM `bot_texts_old` as t LIMIT 1)

UNION ALL SELECT 'payment_payping', (SELECT JSON_OBJECT('choose_amount', (SELECT JSON_OBJECT('value', t.charge_payping)), 'show_invoice', (SELECT JSON_OBJECT('value', t.charge_payping_pay))) FROM `bot_texts_old` as t LIMIT 1)
UNION ALL SELECT 'payment_aqaye_pardakht', (SELECT JSON_OBJECT('choose_amount', (SELECT JSON_OBJECT('value', t.charge_aqayepardakht)), 'show_invoice', (SELECT JSON_OBJECT('value', t.charge_aqayepardakht_pay))) FROM `bot_texts_old` as t LIMIT 1)

) as `temp_texts`
    WHERE EXISTS (SELECT 1 from `bot_texts_old`);


        DROP TABLE IF EXISTS `settings`;
        DROP TABLE IF EXISTS `bot_texts_old`;
        
        DROP PROCEDURE IF EXISTS AddIndexRandomAm;
        DROP PROCEDURE IF EXISTS DeleteIndexRandomAm;

        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `provider` VARCHAR(13) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping\naqayepardakht: aqayepardakht\nzibal: zibal\nmadpal: madpal' DEFAULT 'fastpay';

        ALTER TABLE `servers` ADD `username` VARCHAR(34);
        ALTER TABLE `servers` ADD `password` LONGTEXT;

        ALTER TABLE `users` ADD `blocked_bot` BOOL NOT NULL  DEFAULT 0;
"""


async def downgrade(
    db: BaseDBAsyncClient,
) -> str:  # all settings and texts will be reset on downgrade
    return """
        DROP TABLE IF EXISTS `bot_settings`;
        DROP TABLE IF EXISTS `bot_texts`;
    
        CREATE TABLE `settings` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `created_at` datetime(6) DEFAULT current_timestamp(6),
    `updated_at` datetime(6) DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
    `crypto_payment` tinyint(1) NOT NULL DEFAULT 1,
    `perfectmoney_payment` tinyint(1) NOT NULL DEFAULT 1,
    `cardtocard_payment` tinyint(1) NOT NULL DEFAULT 1,
    `access_only` tinyint(1) NOT NULL DEFAULT 0,
    `referral_system` tinyint(1) NOT NULL DEFAULT 1,
    `default_username_prefix` varchar(20) NOT NULL DEFAULT 'Marzdemo',
    `default_daily_test_services` int(11) NOT NULL DEFAULT 1,
    `transaction_logs` varchar(30) DEFAULT NULL,
    `orders_logs` varchar(30) DEFAULT NULL,
    `perfectmoney_account_id` varchar(40) DEFAULT NULL,
    `perfectmoney_payee_account` varchar(40) DEFAULT NULL,
    `perfectmoney_passphrase` varchar(100) DEFAULT NULL,
    `np_api_key` varchar(128) DEFAULT '7TWKAGZ-CSF4WEM-MQSVVXW-VDRAYNA',
    `np_ipn_secret_key` varchar(256) DEFAULT 'ow6CMnmAeFHQachQmoMsujjbHQ8EpLO/',
    `marzban_webhook_secret` varchar(256) DEFAULT NULL,
    `force_join_chats` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`force_join_chats`)),
    `show_connect_links_button` tinyint(1) NOT NULL DEFAULT 1,
    `reset_password_button` tinyint(1) NOT NULL DEFAULT 1,
    `charge_amount_list` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`charge_amount_list`)),
    `charge_amount_orders` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`charge_amount_orders`)),
    `show_test_service_in_menu` tinyint(1) NOT NULL DEFAULT 1,
    `payping_payment` tinyint(1) NOT NULL DEFAULT 0,
    `payping_api_key` varchar(128) DEFAULT NULL,
    `payping_menu_title` varchar(50) NOT NULL DEFAULT 'درگاه ریالی payping',
    `referral_discount_percent` int(11) NOT NULL DEFAULT 20,
    `cancel_payback_days` int(11) NOT NULL DEFAULT 5,
    `cancel_payback_fee` int(11) NOT NULL DEFAULT 10000,
    `cardtocard_menu_title` varchar(50) NOT NULL DEFAULT '? کارت به کارت',
    `np_menu_title` varchar(50) NOT NULL DEFAULT '? ارز دیجیتال',
    `payping_min_pay_amount` int(11) NOT NULL DEFAULT 20000,
    `np_min_pay_amount` int(11) NOT NULL DEFAULT 20000,
    `cardtocard_min_pay_amount` int(11) NOT NULL DEFAULT 20000,
    `perfectmoney_menu_title` varchar(50) NOT NULL DEFAULT '? ووچر پرفکت‌مانی',
    `cardtocard_free_after_percent` int(11) NOT NULL DEFAULT 0,
    `np_free_after_percent` int(11) NOT NULL DEFAULT 0,
    `perfectmoney_free_after_percent` int(11) NOT NULL DEFAULT 0,
    `np_free_after` int(11) NOT NULL DEFAULT 0,
    `cardtocard_free_after` int(11) NOT NULL DEFAULT 0,
    `payping_free_after_percent` int(11) NOT NULL DEFAULT 0,
    `payping_free_after` int(11) NOT NULL DEFAULT 0,
    `perfectmoney_free_after` int(11) NOT NULL DEFAULT 0,
    `remind_invoices_each_n_days` int(11) NOT NULL DEFAULT 3,
    `disable_users_role` smallint(6) NOT NULL DEFAULT 1 COMMENT 'user: 0\nreseller: 1\nadmin: 2\nsuper_user: 3',
    `remind_invoices_after_amount` bigint(20) NOT NULL DEFAULT 1000000,
    `username_generator` varchar(11) NOT NULL DEFAULT 'randomized' COMMENT 'randomized: randomized\nincremental: incremental',
    `aqayepardakht_menu_title` varchar(50) NOT NULL DEFAULT 'درگاه ریالی aqayepardakht',
    `aqayepardakht_free_after` int(11) NOT NULL DEFAULT 0,
    `aqayepardakht_free_after_percent` int(11) NOT NULL DEFAULT 0,
    `aqayepardakht_min_pay_amount` int(11) NOT NULL DEFAULT 20000,
    `aqayepardakht_api_key` varchar(128) DEFAULT NULL,
    `aqayepardakht_payment` tinyint(1) NOT NULL DEFAULT 0,
    `swapino_min_pay_amount` int(11) NOT NULL DEFAULT 20000,
    `eswap_menu_title` varchar(50) NOT NULL DEFAULT 'درگاه ریالی eswap',
    `eswap_min_pay_amount` int(11) NOT NULL DEFAULT 20000,
    `swapino_free_after_percent` int(11) NOT NULL DEFAULT 0,
    `swapino_payment` tinyint(1) NOT NULL DEFAULT 0,
    `eswap_free_after_percent` int(11) NOT NULL DEFAULT 0,
    `swapino_menu_title` varchar(50) NOT NULL DEFAULT 'درگاه ریالی swapino',
    `swapino_free_after` int(11) NOT NULL DEFAULT 0,
    `eswap_payment` tinyint(1) NOT NULL DEFAULT 0,
    `swapino_api_key` varchar(128) DEFAULT NULL,
    `eswap_api_key` varchar(128) DEFAULT NULL,
    `eswap_free_after` int(11) NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`)
) CHARACTER SET utf8mb4;
        
        CREATE TABLE `bot_texts` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `created_at` datetime(6) DEFAULT current_timestamp(6),
    `updated_at` datetime(6) DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
    `start` longtext NOT NULL,
    `main_menu` longtext NOT NULL,
    `force_join` longtext NOT NULL,
    `purchase` longtext NOT NULL,
    `support` longtext NOT NULL,
    `help` longtext NOT NULL,
    `command_not_found` longtext NOT NULL,
    `charge` longtext NOT NULL,
    `charge_payping` longtext NOT NULL,
    `charge_payping_pay` longtext NOT NULL,
    `charge_crypto` longtext NOT NULL,
    `charge_cardtocard` longtext NOT NULL,
    `charge_perfectmoney` longtext NOT NULL,
    `charge_crypto_pay` longtext NOT NULL,
    `charge_cardtocard_pay` longtext NOT NULL,
    `show_proxy_help` longtext NOT NULL,
    `referral_banner_text` longtext NOT NULL,
    `charge_aqayepardakht` longtext NOT NULL,
    `charge_aqayepardakht_pay` longtext NOT NULL,
    `charge_swapino_pay` longtext NOT NULL,
    `charge_eswap` longtext NOT NULL,
    `charge_swapino` longtext NOT NULL,
    `charge_eswap_pay` longtext NOT NULL,
    PRIMARY KEY (`id`)
) CHARACTER SET utf8mb4;


        DROP TABLE IF EXISTS `services_to_menues`;
        DROP TABLE IF EXISTS `user_to_service_menues`;
        DROP TABLE IF EXISTS `service_menues`;
        
        ALTER TABLE `rialgateway_payments` MODIFY COLUMN `provider` VARCHAR(13) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping\naqayepardakht: aqayepardakht\nmadpal: madpal' DEFAULT 'fastpay';

        ALTER TABLE `servers` DROP COLUMN `username`;
        ALTER TABLE `servers` DROP COLUMN `password`;

        ALTER TABLE `users` DROP COLUMN `blocked_bot`;
        """
