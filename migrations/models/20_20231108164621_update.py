from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `discounts` (
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `is_active` BOOL NOT NULL  DEFAULT 1,
    `percentage` INT NOT NULL,
    `expires_at` DATETIME(6)
) CHARACTER SET utf8mb4;
        CREATE TABLE `service_discounts` (
    `service_id` INT NOT NULL REFERENCES `services` (`id`) ON DELETE CASCADE,
    `discounts_id` INT NOT NULL REFERENCES `discounts` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        CREATE TABLE `proxy_discounts` (
    `proxy_id` INT NOT NULL REFERENCES `proxies` (`id`) ON DELETE CASCADE,
    `discounts_id` INT NOT NULL REFERENCES `discounts` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `proxy_discounts`;
        DROP TABLE IF EXISTS `service_discounts`;
        DROP TABLE IF EXISTS `discounts`;"""
