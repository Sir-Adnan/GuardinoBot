from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `payments_rialgateway` MODIFY COLUMN `provider` VARCHAR(13) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping\naqayepardakht: aqayepardakht\nzibal: zibal\nmadpal: madpal\nzarinpal: zarinpal' DEFAULT 'fastpay';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `payments_rialgateway` MODIFY COLUMN `provider` VARCHAR(13) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping\naqayepardakht: aqayepardakht\nzibal: zibal\nmadpal: madpal' DEFAULT 'fastpay';"""
