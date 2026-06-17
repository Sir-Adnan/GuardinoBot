from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `transactions` MODIFY COLUMN `status` SMALLINT NOT NULL  COMMENT 'waiting: 1\nfailed: 2\ncanceled: 3\npartially_paid: 4\nfinished: 5\nrejected: 6\nsending: 7\nconfirming: 8' DEFAULT 1;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `transactions` MODIFY COLUMN `status` SMALLINT NOT NULL  COMMENT 'waiting: 1\nfailed: 2\ncanceled: 3\npartially_paid: 4\nfinished: 5\nrejected: 6' DEFAULT 1;"""
