from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` ADD `charge_amount_list` JSON;
        ALTER TABLE `settings` ADD `charge_amount_orders` JSON;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `settings` DROP COLUMN `charge_amount_list`;
        ALTER TABLE `settings` DROP COLUMN `charge_amount_orders`;"""
