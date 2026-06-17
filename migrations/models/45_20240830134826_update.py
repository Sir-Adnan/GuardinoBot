from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` ADD `priority` INT NOT NULL  DEFAULT 1000000;
        
        UPDATE `payment_transactions` SET `amount_paid` = `amount` WHERE type=5 AND amount_paid is null;
        
        """  # fix by_admin payments.amount_paid field for old records


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `services` DROP COLUMN `priority`;"""
