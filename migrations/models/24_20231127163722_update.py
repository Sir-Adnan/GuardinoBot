from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `servers` ADD `total_proxies` INT NOT NULL  DEFAULT 0;
        UPDATE `servers` SET servers.total_proxies = (SELECT COUNT(*) from `proxies` WHERE `servers`.id = `proxies`.`server_id`);
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `servers` DROP COLUMN `total_proxies`;"""
