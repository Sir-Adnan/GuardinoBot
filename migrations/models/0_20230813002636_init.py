from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `users` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `username` VARCHAR(200),
    `name` VARCHAR(200),
    `phone_number` VARCHAR(14),
    `balance` INT NOT NULL  DEFAULT 0,
    `total_spent` INT NOT NULL  DEFAULT 0,
    `is_blocked` BOOL NOT NULL  DEFAULT 0,
    `is_postpaid` BOOL NOT NULL  DEFAULT 0,
    `max_post_paid_credit` INT NOT NULL  DEFAULT 5000000,
    `gift_given_to_referrer` BOOL NOT NULL  DEFAULT 0,
    `role` SMALLINT NOT NULL  COMMENT 'user: 0\nreseller: 1\nadmin: 2\nsuper_user: 3' DEFAULT 0,
    `force_join_check` DATETIME(6),
    `parent_id` BIGINT,
    `referrer_id` BIGINT,
    CONSTRAINT `fk_users_users_b2a9ae01` FOREIGN KEY (`parent_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_users_users_c3ec4157` FOREIGN KEY (`referrer_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `transactions` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6',
    `status` SMALLINT NOT NULL  COMMENT 'waiting: 1\nfailed: 2\ncanceled: 3\npartially_paid: 4\nfinished: 5' DEFAULT 1,
    `finished_at` DATETIME(6),
    `amount` INT NOT NULL,
    `amount_paid` INT,
    `amount_free_given` INT NOT NULL  DEFAULT 0,
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_transact_users_6189e5a9` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `byadmin_payments` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 5,
    `by_admin_id` BIGINT,
    `transaction_id` BIGINT NOT NULL UNIQUE,
    CONSTRAINT `fk_byadmin__users_22c9072e` FOREIGN KEY (`by_admin_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_byadmin__transact_617e558f` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `crypto_payments` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 1,
    `usdt_rate` INT NOT NULL,
    `invoice_id` VARCHAR(64) NOT NULL,
    `order_id` VARCHAR(64),
    `price_amount` DOUBLE NOT NULL,
    `price_currency` VARCHAR(20) NOT NULL,
    `nowpm_created_at` DATETIME(6),
    `pay_currency` VARCHAR(32),
    `pay_amount` DOUBLE,
    `order_description` VARCHAR(64),
    `nowpm_updated_at` DATETIME(6),
    `payment_status` SMALLINT NOT NULL  COMMENT 'waiting: 0\nconfirming: 1\nconfirmed: 2\nsending: 3\npartially_paid: 4\nfinished: 5\nfailed: 6\nrefunded: 7\nexpired: 8' DEFAULT 0,
    `outcome_amount` DOUBLE,
    `outcome_currency` VARCHAR(20),
    `purchase_id` VARCHAR(64),
    `pay_address` VARCHAR(128),
    `transaction_id` BIGINT NOT NULL UNIQUE,
    CONSTRAINT `fk_crypto_p_transact_d08038fb` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `gift_payments` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 6,
    `gift_type` SMALLINT NOT NULL  COMMENT 'referral: 1' DEFAULT 1,
    `invitee_id` BIGINT,
    `transaction_id` BIGINT NOT NULL UNIQUE,
    CONSTRAINT `fk_gift_pay_users_645026e1` FOREIGN KEY (`invitee_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_gift_pay_transact_28bc9be2` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `perfectmoney_payments` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 3,
    `usd_rate` INT NOT NULL,
    `payee_account` VARCHAR(64) NOT NULL,
    `ev_number` VARCHAR(64) NOT NULL,
    `ev_code` VARCHAR(64) NOT NULL,
    `ev_amount_currency` VARCHAR(32),
    `payment_batch_number` VARCHAR(64),
    `transaction_id` BIGINT NOT NULL UNIQUE,
    CONSTRAINT `fk_perfectm_transact_b998699c` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `user_settings` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `proxy_username_prefix` VARCHAR(25),
    `discount_percentage` INT NOT NULL  DEFAULT 0,
    `proxy_list_sort_by` VARCHAR(20)   COMMENT 'created_ascending: created_at\ncreated_descending: -created_at\nrenewed_ascending: renewed_at\nrenewed_descending: -renewed_at' DEFAULT 'created_at',
    `user_id` BIGINT NOT NULL  PRIMARY KEY,
    CONSTRAINT `fk_user_set_users_9237a864` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `servers` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `host` VARCHAR(64) NOT NULL,
    `port` INT,
    `token` VARCHAR(512) NOT NULL,
    `https` BOOL NOT NULL  DEFAULT 0,
    `name` VARCHAR(200),
    `is_enabled` BOOL NOT NULL  DEFAULT 1
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `services` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `name` VARCHAR(64) NOT NULL,
    `data_limit` BIGINT NOT NULL,
    `expire_duration` INT NOT NULL,
    `inbounds` JSON NOT NULL,
    `flow` VARCHAR(20)   COMMENT 'none: None\nxtls_rprx_vision: xtls-rprx-vision' DEFAULT 'None',
    `price` INT NOT NULL,
    `one_time_only` BOOL NOT NULL  DEFAULT 0,
    `purchaseable` BOOL NOT NULL  DEFAULT 0,
    `renewable` BOOL NOT NULL  DEFAULT 0,
    `resellers_only` BOOL NOT NULL  DEFAULT 0,
    `users_only` BOOL NOT NULL  DEFAULT 0,
    `server_id` BIGINT NOT NULL,
    CONSTRAINT `fk_services_servers_be0c61a1` FOREIGN KEY (`server_id`) REFERENCES `servers` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `cards` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `card_number` VARCHAR(16) NOT NULL,
    `card_holder` VARCHAR(128) NOT NULL,
    `is_active` BOOL NOT NULL  DEFAULT 1
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `cardtocard_payments` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `type` SMALLINT NOT NULL  COMMENT 'crypto: 1\ncard_to_card: 2\nperfectmoney: 3\nrial_gateway: 4\nby_admin: 5\ngift: 6' DEFAULT 2,
    `random_amount` INT NOT NULL UNIQUE,
    `destination_card_id` INT,
    `transaction_id` BIGINT NOT NULL UNIQUE,
    CONSTRAINT `fk_cardtoca_cards_d4b2d100` FOREIGN KEY (`destination_card_id`) REFERENCES `cards` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_cardtoca_transact_5ba13d14` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE,
    KEY `idx_cardtocard__random__91bac8` (`random_amount`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `proxies` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `custom_name` VARCHAR(64),
    `username` VARCHAR(32) NOT NULL UNIQUE,
    `cost` INT,
    `status` VARCHAR(12) NOT NULL  COMMENT 'active: active\ndisabled: disabled\nlimited: limited\nexpired: expired' DEFAULT 'active',
    `renewed_at` DATETIME(6),
    `server_id` BIGINT NOT NULL,
    `service_id` INT,
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_proxies_servers_43cfb161` FOREIGN KEY (`server_id`) REFERENCES `servers` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_proxies_services_338cef03` FOREIGN KEY (`service_id`) REFERENCES `services` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_proxies_users_b8af88b7` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    KEY `idx_proxies_usernam_c3e1f3` (`username`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `invoices` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `amount` INT NOT NULL,
    `type` SMALLINT NOT NULL  COMMENT 'purchase: 1\nrenew_now: 2\nrenew_reserve: 3\nparent_charged_child: 4' DEFAULT 1,
    `is_paid` BOOL NOT NULL  DEFAULT 0,
    `proxy_id` INT,
    `transaction_id` BIGINT,
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_invoices_proxies_dfa62f0f` FOREIGN KEY (`proxy_id`) REFERENCES `proxies` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_invoices_transact_dbab496e` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_invoices_users_b9efcef2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `reserves` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `activate_at` DATETIME(6) NOT NULL,
    `invoice_id` INT NOT NULL,
    `service_id` INT NOT NULL,
    `user_id` BIGINT NOT NULL,
    `proxy_id` INT NOT NULL  PRIMARY KEY,
    CONSTRAINT `fk_reserves_invoices_5e65035f` FOREIGN KEY (`invoice_id`) REFERENCES `invoices` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_reserves_services_94b4f85b` FOREIGN KEY (`service_id`) REFERENCES `services` (`id`) ON DELETE RESTRICT,
    CONSTRAINT `fk_reserves_users_291df1c4` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_reserves_proxies_c3869fe4` FOREIGN KEY (`proxy_id`) REFERENCES `proxies` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `aerich` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `version` VARCHAR(255) NOT NULL,
    `app` VARCHAR(100) NOT NULL,
    `content` JSON NOT NULL
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
