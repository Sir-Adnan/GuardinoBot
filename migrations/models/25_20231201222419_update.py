from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `purchase_logs` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `type` VARCHAR(8) NOT NULL  COMMENT 'purchase: purchase\nrenew: renew\nreserve: reserve' DEFAULT 'purchase',
    `amount` DOUBLE NOT NULL  DEFAULT 0,
    `data` BIGINT,
    `proxy_id` INT,
    `service_id` INT,
    `user_id` BIGINT,
    CONSTRAINT `fk_purchase_proxies_527283b3` FOREIGN KEY (`proxy_id`) REFERENCES `proxies` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_purchase_services_cafa6499` FOREIGN KEY (`service_id`) REFERENCES `services` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_purchase_users_5cd5f1bd` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `purchase_logs`;"""
