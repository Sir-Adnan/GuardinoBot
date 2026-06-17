from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `crypto_payments` ADD `fee` JSON;
        ALTER TABLE `settings` ALTER COLUMN `np_ipn_secret_key` SET DEFAULT 'ow6CMnmAeFHQachQmoMsujjbHQ8EpLO/';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `crypto_payments` DROP COLUMN `fee`;
        ALTER TABLE `settings` ALTER COLUMN `np_ipn_secret_key` SET DEFAULT '9fa66YgjqU8mlLHFRihG0jeFjg+cHbxY';"""
