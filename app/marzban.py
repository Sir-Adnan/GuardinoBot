from aiogram import Dispatcher

from app.models.server import Server
from marzban_client import AuthenticatedClient


class ServerAuthenticationError(Exception):
    def __init__(self, *args: object, server_id: int) -> None:
        self.server_id = server_id
        super().__init__(*args)


class Marzban:
    servers: dict[int, AuthenticatedClient] = dict()

    @classmethod
    def init_servers(cls, servers: list[Server]) -> None:
        for server in servers:
            cls.servers.update(
                {
                    server.id: AuthenticatedClient(
                        base_url=server.url,
                        token=server.token,
                        raise_on_unexpected_status=True,
                    )
                }
            )

    @classmethod
    async def refresh_servers(cls) -> None:
        """refresh servers from database"""
        servers = await Server.all()
        cls.servers.clear()
        cls.init_servers(servers)

    @classmethod
    def get_servers(cls) -> dict[int, AuthenticatedClient]:
        """get Marzban server instances"""
        return cls.servers

    @classmethod
    def get_server(cls, id: int = None) -> "Marzban":
        if (server := cls.servers.get(id, None)) is None:
            raise KeyError(f"Server with id of '{id}' not found!")
        return server


def setup_api(dp: Dispatcher) -> None:
    from app.panels.registry import PanelRegistry

    dp.startup.register(Marzban.refresh_servers)
    dp.startup.register(PanelRegistry.refresh)
    dp.shutdown.register(PanelRegistry.aclose_all)
