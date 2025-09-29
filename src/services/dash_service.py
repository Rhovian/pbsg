"""Legacy Dash web framework service - redirects to modular dashboard"""

from typing import Optional
from loguru import logger
from sqlalchemy.engine import Engine

from .dashboard import DashboardService
from .data_sources.storage import IntegratedOHLCStorage


class DashService:
    """
    Legacy service wrapper for backward compatibility.
    Redirects to the new modular DashboardService.
    """

    def __init__(
        self,
        engine: Optional[Engine] = None,
        storage: Optional[IntegratedOHLCStorage] = None,
        debug: bool = False,
    ) -> None:
        """
        Initialize dashboard service

        Args:
            engine: SQLAlchemy database engine (required for data connectivity)
            storage: Optional integrated storage for stats
            debug: Enable debug mode
        """
        if engine is None:
            logger.warning(
                "DashService initialized without database engine. "
                "Dashboard will show empty charts. "
                "Pass an SQLAlchemy engine to connect to your data sources."
            )

        self.dashboard_service = DashboardService(
            engine=engine, storage=storage, debug=debug
        )

    def run(self, host: str = "127.0.0.1", port: int = 8050) -> None:
        """Run the Dash application"""
        self.dashboard_service.run(host=host, port=port)

    def get_app(self):
        """Get the Dash application instance"""
        return self.dashboard_service.get_app()

    def get_data_manager(self):
        """Get the data manager instance"""
        return self.dashboard_service.get_data_manager()

    def clear_cache(self) -> None:
        """Clear data cache"""
        self.dashboard_service.clear_cache()
