from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `cardtocard_payments` MODIFY COLUMN `random_amount` BIGINT NOT NULL;
        ALTER TABLE `crypto_payments` ADD `payment_id` VARCHAR(64);
        ALTER TABLE `crypto_payments` MODIFY COLUMN `invoice_id` VARCHAR(64);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `cardtocard_payments` MODIFY COLUMN `random_amount` INT NOT NULL;
        ALTER TABLE `crypto_payments` DROP COLUMN `payment_id`;
        ALTER TABLE `crypto_payments` MODIFY COLUMN `invoice_id` VARCHAR(64) NOT NULL;"""
