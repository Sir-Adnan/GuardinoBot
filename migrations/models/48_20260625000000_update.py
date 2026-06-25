from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `audit_logs` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6)   DEFAULT CURRENT_TIMESTAMP(6),
    `actor_role` INT NOT NULL  DEFAULT 0,
    `source` VARCHAR(8) NOT NULL  DEFAULT 'web',
    `action` VARCHAR(64) NOT NULL,
    `target_type` VARCHAR(32),
    `target_id` VARCHAR(64),
    `target_label` VARCHAR(128),
    `amount` DOUBLE,
    `detail` JSON,
    `actor_id` BIGINT,
    CONSTRAINT `fk_auditlog_users_1a2b3c4d` FOREIGN KEY (`actor_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    KEY `idx_audit_action` (`action`),
    KEY `idx_audit_created` (`created_at`)
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `audit_logs`;"""
