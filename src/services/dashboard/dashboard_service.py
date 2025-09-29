"""Modular Dash web framework service for creating interactive dashboards"""

import dash
from dash import dcc, html, Input, Output
from typing import Optional
from loguru import logger
from sqlalchemy.engine import Engine

from .data_manager import DataManager
from .components import ChartComponents
from ..data_sources.storage import IntegratedOHLCStorage


class DashboardService:
    """Modular service for creating and managing Dash web applications"""

    def __init__(
        self,
        engine: Engine,
        storage: Optional[IntegratedOHLCStorage] = None,
        debug: bool = False,
    ) -> None:
        """
        Initialize dashboard service

        Args:
            engine: SQLAlchemy database engine
            storage: Optional integrated storage for stats
            debug: Enable debug mode
        """
        self.app = dash.Dash(__name__)
        self.debug = debug
        self.data_manager = DataManager(engine, storage)
        self.chart_components = ChartComponents()

        # Configure app
        self._configure_app()
        self._setup_layout()
        self._setup_callbacks()

    def _configure_app(self) -> None:
        """Configure the Dash application"""
        # Add custom CSS
        self.app.index_string = """
        <!DOCTYPE html>
        <html>
            <head>
                {%metas%}
                <title>PBSG Dashboard</title>
                {%favicon%}
                {%css%}
                <style>
                    body {
                        margin: 0;
                        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                        background-color: #1e1e1e;
                        color: #ffffff;
                    }
                    .container {
                        padding: 20px;
                        max-width: 1400px;
                        margin: 0 auto;
                    }
                    .header {
                        text-align: center;
                        margin-bottom: 30px;
                        padding: 20px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 10px;
                    }
                    .controls {
                        display: flex;
                        gap: 20px;
                        margin-bottom: 20px;
                        flex-wrap: wrap;
                        align-items: center;
                    }
                    .control-group {
                        display: flex;
                        flex-direction: column;
                        gap: 5px;
                    }
                    .control-label {
                        font-weight: bold;
                        color: #cccccc;
                    }
                    .charts-container {
                        display: grid;
                        grid-template-columns: 1fr;
                        gap: 20px;
                    }
                    .stats-container {
                        display: flex;
                        gap: 20px;
                        margin-bottom: 20px;
                        flex-wrap: wrap;
                    }
                    .stats-card {
                        background: #2d2d2d;
                        padding: 20px;
                        border-radius: 8px;
                        text-align: center;
                        min-width: 150px;
                        flex: 1;
                    }
                    .card-title {
                        margin: 0 0 10px 0;
                        color: #cccccc;
                        font-size: 14px;
                    }
                    .card-value {
                        margin: 0 0 5px 0;
                        color: #00D4AA;
                        font-size: 24px;
                        font-weight: bold;
                    }
                    .card-subtitle {
                        margin: 0;
                        color: #888888;
                        font-size: 12px;
                    }
                    .chart-container {
                        background: #2d2d2d;
                        border-radius: 8px;
                        padding: 10px;
                    }
                </style>
            </head>
            <body>
                {%app_entry%}
                <footer>
                    {%config%}
                    {%scripts%}
                    {%renderer%}
                </footer>
            </body>
        </html>
        """

    def _setup_layout(self) -> None:
        """Setup the layout for the Dash application"""
        # Get available symbols
        available_symbols = self.data_manager.get_available_symbols()

        self.app.layout = html.Div(
            [
                # Header
                html.Div(
                    [
                        html.H1(
                            "PBSG Dashboard", style={"margin": "0", "color": "white"}
                        ),
                        html.P(
                            "Real-time Cryptocurrency Trading Dashboard",
                            style={"margin": "10px 0 0 0", "opacity": "0.8"},
                        ),
                    ],
                    className="header",
                ),
                # Controls
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label("Symbol:", className="control-label"),
                                self.chart_components.create_symbol_dropdown(
                                    available_symbols
                                ),
                            ],
                            className="control-group",
                        ),
                        html.Div(
                            [
                                html.Label("Chart Type:", className="control-label"),
                                self.chart_components.create_chart_type_dropdown(),
                            ],
                            className="control-group",
                        ),
                        html.Div(
                            [
                                html.Label("Interval:", className="control-label"),
                                self.chart_components.create_interval_selector(),
                            ],
                            className="control-group",
                        ),
                        html.Div(
                            [
                                html.Label("Records:", className="control-label"),
                                dcc.Dropdown(
                                    id="limit-dropdown",
                                    options=[
                                        {"label": "50", "value": 50},
                                        {"label": "100", "value": 100},
                                        {"label": "200", "value": 200},
                                        {"label": "500", "value": 500},
                                    ],
                                    value=100,
                                    clearable=False,
                                    className="limit-dropdown",
                                ),
                            ],
                            className="control-group",
                        ),
                    ],
                    className="controls",
                ),
                # Statistics cards
                html.Div(id="stats-cards"),
                # Charts
                html.Div(
                    [
                        html.Div(
                            [dcc.Graph(id="price-chart")], className="chart-container"
                        ),
                        html.Div(
                            [dcc.Graph(id="volume-chart")], className="chart-container"
                        ),
                    ],
                    className="charts-container",
                ),
                # Auto-refresh interval
                dcc.Interval(
                    id="interval-component",
                    interval=10 * 1000,  # Update every 10 seconds
                    n_intervals=0,
                ),
            ],
            className="container",
        )

    def _setup_callbacks(self) -> None:
        """Setup Dash callbacks for interactivity"""

        @self.app.callback(
            [
                Output("price-chart", "figure"),
                Output("volume-chart", "figure"),
                Output("stats-cards", "children"),
            ],
            [
                Input("symbol-dropdown", "value"),
                Input("chart-type-dropdown", "value"),
                Input("interval-dropdown", "value"),
                Input("limit-dropdown", "value"),
                Input("interval-component", "n_intervals"),
            ],
        )
        def update_dashboard(
            selected_symbol: str,
            chart_type: str,
            interval_minutes: int,
            limit: int,
            n: int,
        ) -> tuple:
            """Update all dashboard components"""
            logger.debug(
                f"Updating dashboard: symbol={selected_symbol}, "
                f"type={chart_type}, interval={interval_minutes}, limit={limit}"
            )

            try:
                # Get OHLC data
                ohlc_data = self.data_manager.get_latest_ohlc_data(
                    symbol=selected_symbol,
                    limit=limit,
                    interval_minutes=interval_minutes,
                )

                # Get volume data
                volume_data = self.data_manager.get_volume_data(
                    symbol=selected_symbol,
                    limit=limit,
                    interval_minutes=interval_minutes,
                )

                # Get latest price
                latest_price = self.data_manager.get_latest_price(selected_symbol)

                # Get storage stats
                storage_stats = self.data_manager.get_storage_stats()

                # Create charts
                price_chart = self.chart_components.create_price_chart(
                    data=ohlc_data, symbol=selected_symbol, chart_type=chart_type
                )

                volume_chart = self.chart_components.create_volume_chart(
                    data=volume_data, symbol=selected_symbol
                )

                # Create stats cards
                stats_cards = self.chart_components.create_stats_cards(
                    latest_price=latest_price,
                    symbol=selected_symbol,
                    storage_stats=storage_stats,
                )

                return price_chart, volume_chart, stats_cards

            except Exception as e:
                logger.error(f"Error updating dashboard: {e}")

                # Return empty charts on error
                empty_price = self.chart_components._empty_figure(
                    f"{selected_symbol} Price Chart", "Error loading data"
                )
                empty_volume = self.chart_components._empty_figure(
                    f"{selected_symbol} Volume Chart", "Error loading data"
                )
                empty_stats = html.Div("Error loading statistics")

                return empty_price, empty_volume, empty_stats

    def run(self, host: str = "127.0.0.1", port: int = 8050) -> None:
        """Run the Dash application"""
        logger.info(f"Starting modular dashboard server on {host}:{port}")
        self.app.run(debug=self.debug, host=host, port=port)

    def get_app(self) -> dash.Dash:
        """Get the Dash application instance"""
        return self.app

    def get_data_manager(self) -> DataManager:
        """Get the data manager instance"""
        return self.data_manager

    def clear_cache(self) -> None:
        """Clear data cache"""
        self.data_manager.clear_cache()
        logger.info("Dashboard cache cleared")
