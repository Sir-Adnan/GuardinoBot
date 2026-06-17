from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` MODIFY COLUMN `expire_duration` BIGINT NOT NULL;
        ALTER TABLE `settings` ADD `cancel_payback_days` INT NOT NULL  DEFAULT 5;
        ALTER TABLE `settings` ADD `cancel_payback_fee` INT NOT NULL  DEFAULT 10000;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` MODIFY COLUMN `expire_duration` INT NOT NULL;
        ALTER TABLE `settings` DROP COLUMN `cancel_payback_days`;
        ALTER TABLE `settings` DROP COLUMN `cancel_payback_fee`;"""
