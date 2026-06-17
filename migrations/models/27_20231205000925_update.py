from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `bot_texts` ADD `referral_banner_text` LONGTEXT NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `bot_texts` DROP COLUMN `referral_banner_text`;"""
