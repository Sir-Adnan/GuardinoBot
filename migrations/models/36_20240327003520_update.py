from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `invoices` ADD `service_id` INT;
        ALTER TABLE `invoices` ADD `is_draft` BOOL NOT NULL  DEFAULT 0;
        ALTER TABLE `service_menues` ALTER COLUMN `renew` SET DEFAULT 1;
        ALTER TABLE `invoices` ADD CONSTRAINT `fk_invoices_services_063cc288` FOREIGN KEY (`service_id`) REFERENCES `services` (`id`) ON DELETE SET NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `invoices` DROP FOREIGN KEY `fk_invoices_services_063cc288`;
        ALTER TABLE `invoices` DROP COLUMN `service_id`;
        ALTER TABLE `invoices` DROP COLUMN `is_draft`;
        ALTER TABLE `service_menues` ALTER COLUMN `renew` SET DEFAULT 0;"""
