from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` ADD `referral_discount_percent` INT NOT NULL  DEFAULT 20;
        ALTER TABLE `settings` MODIFY COLUMN `fastpay_encryption_key` VARCHAR(256);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` DROP COLUMN `referral_discount_percent`;
        ALTER TABLE `settings` MODIFY COLUMN `fastpay_encryption_key` VARCHAR(128);"""
