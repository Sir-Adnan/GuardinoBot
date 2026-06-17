from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `payments_rialgateway` MODIFY COLUMN `provider` VARCHAR(14) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping\naqaye_pardakht: aqaye_pardakht\nzibal: zibal\nmadpal: madpal\nzarinpal: zarinpal' DEFAULT 'fastpay';
        UPDATE payments_rialgateway SET provider='aqaye_pardakht' WHERE provider='aqayepardakht';
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE payments_rialgateway SET provider='aqayepardakht' WHERE provider='aqaye_pardakht';
        ALTER TABLE `payments_rialgateway` MODIFY COLUMN `provider` VARCHAR(13) NOT NULL  COMMENT 'fastpay: fastpay\nswapwallet: swapwallet\npayping: payping\naqayepardakht: aqayepardakht\nzibal: zibal\nmadpal: madpal\nzarinpal: zarinpal' DEFAULT 'fastpay';"""
