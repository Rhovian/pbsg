"""Dashboard chart components and layouts"""

from typing import Dict, List, Any, Optional
import plotly.graph_objs as go
from dash import dcc, html
from loguru import logger


class ChartComponents:
    """Factory for creating dashboard chart components"""

    @staticmethod
    def create_price_chart(
        data: List[Dict[str, Any]], symbol: str, chart_type: str = "candlestick"
    ) -> Dict[str, Any]:
        """
        Create a price chart figure

        Args:
            data: OHLC data list
            symbol: Trading symbol
            chart_type: 'candlestick', 'line', or 'ohlc'

        Returns:
            Plotly figure dictionary
        """
        if not data:
            return ChartComponents._empty_figure(
                f"{symbol} Price Chart", "No data available"
            )

        try:
            # Optimize for large datasets
            optimized_data = ChartComponents._optimize_data_for_chart(data)
            timestamps = [item["timestamp"] for item in optimized_data]

            fig = go.Figure()

            # Use WebGL for better performance with large datasets
            use_webgl = len(optimized_data) > 10000

            if chart_type == "candlestick":
                fig.add_trace(
                    go.Candlestick(
                        x=timestamps,
                        open=[item["open"] for item in optimized_data],
                        high=[item["high"] for item in optimized_data],
                        low=[item["low"] for item in optimized_data],
                        close=[item["close"] for item in optimized_data],
                        name=symbol,
                        increasing_line_color="#00D4AA",
                        decreasing_line_color="#FF6B6B",
                    )
                )
            elif chart_type == "line":
                trace_class = go.Scattergl if use_webgl else go.Scatter
                fig.add_trace(
                    trace_class(
                        x=timestamps,
                        y=[item["close"] for item in optimized_data],
                        mode="lines",
                        name=f"{symbol} Close Price",
                        line=dict(color="#1f77b4", width=2),
                    )
                )
            elif chart_type == "ohlc":
                fig.add_trace(
                    go.Ohlc(
                        x=timestamps,
                        open=[item["open"] for item in optimized_data],
                        high=[item["high"] for item in optimized_data],
                        low=[item["low"] for item in optimized_data],
                        close=[item["close"] for item in optimized_data],
                        name=symbol,
                    )
                )

            # Optimize layout for large datasets
            layout_config = {
                "title": f"{symbol} Price Chart ({len(optimized_data):,} points)",
                "xaxis_title": "Time",
                "yaxis_title": "Price (USD)",
                "xaxis_rangeslider_visible": False,
                "height": 500,
                "template": "plotly_dark",
                "font": dict(size=12),
                "margin": dict(l=0, r=0, t=40, b=0),
            }

            # Disable some features for very large datasets to improve performance
            if len(optimized_data) > 50000:
                layout_config.update(
                    {
                        "xaxis": {"showspikes": False},
                        "yaxis": {"showspikes": False},
                        "hovermode": False,
                    }
                )

            fig.update_layout(**layout_config)

            return fig

        except Exception as e:
            logger.error(f"Error creating price chart: {e}")
            return ChartComponents._empty_figure(
                f"{symbol} Price Chart", "Error loading data"
            )

    @staticmethod
    def create_volume_chart(data: List[Dict[str, Any]], symbol: str) -> Dict[str, Any]:
        """
        Create a volume chart figure

        Args:
            data: Volume data list
            symbol: Trading symbol

        Returns:
            Plotly figure dictionary
        """
        if not data:
            return ChartComponents._empty_figure(
                f"{symbol} Volume Chart", "No data available"
            )

        try:
            # Optimize for large datasets
            optimized_data = ChartComponents._optimize_data_for_chart(data)
            timestamps = [item["timestamp"] for item in optimized_data]
            volumes = [item["volume"] for item in optimized_data]

            fig = go.Figure()

            # Bar charts don't have WebGL equivalent, but we still optimize the layout

            fig.add_trace(
                go.Bar(
                    x=timestamps,
                    y=volumes,
                    name="Volume",
                    marker_color="#636EFA",
                    opacity=0.7,
                )
            )

            # Optimize layout for large datasets
            layout_config = {
                "title": f"{symbol} Volume Chart ({len(optimized_data):,} points)",
                "xaxis_title": "Time",
                "yaxis_title": "Volume",
                "height": 300,
                "template": "plotly_dark",
                "font": dict(size=12),
                "margin": dict(l=0, r=0, t=40, b=0),
            }

            # Disable some features for very large datasets
            if len(optimized_data) > 50000:
                layout_config.update(
                    {
                        "xaxis": {"showspikes": False},
                        "yaxis": {"showspikes": False},
                        "hovermode": False,
                    }
                )

            fig.update_layout(**layout_config)

            return fig

        except Exception as e:
            logger.error(f"Error creating volume chart: {e}")
            return ChartComponents._empty_figure(
                f"{symbol} Volume Chart", "Error loading data"
            )

    @staticmethod
    def create_stats_cards(
        latest_price: Optional[Dict[str, Any]],
        symbol: str,
        storage_stats: Optional[Dict[str, Any]] = None,
    ) -> html.Div:
        """
        Create statistics cards

        Args:
            latest_price: Latest price data
            symbol: Trading symbol
            storage_stats: Storage statistics

        Returns:
            Dash HTML div with stats cards
        """
        cards = []

        # Price card
        if latest_price:
            price_card = html.Div(
                [
                    html.H4("Latest Price", className="card-title"),
                    html.H2(f"${latest_price['price']:,.2f}", className="card-value"),
                    html.P(
                        f"Volume: {latest_price['volume']:,.2f}",
                        className="card-subtitle",
                    ),
                ],
                className="stats-card",
            )
            cards.append(price_card)

        # Storage stats cards
        if storage_stats and "integrated" in storage_stats:
            integrated_stats = storage_stats["integrated"]

            # Acceptance rate card
            acceptance_rate = integrated_stats.get("acceptance_rate", 0) * 100
            acceptance_card = html.Div(
                [
                    html.H4("Data Acceptance", className="card-title"),
                    html.H2(f"{acceptance_rate:.1f}%", className="card-value"),
                    html.P(
                        f"Accepted: {integrated_stats.get('total_accepted', 0)}",
                        className="card-subtitle",
                    ),
                ],
                className="stats-card",
            )
            cards.append(acceptance_card)

            # Buffered data card
            buffered_card = html.Div(
                [
                    html.H4("Buffered Records", className="card-title"),
                    html.H2(
                        f"{integrated_stats.get('currently_buffered', 0)}",
                        className="card-value",
                    ),
                    html.P(
                        f"Total Flushed: {integrated_stats.get('total_flushed', 0)}",
                        className="card-subtitle",
                    ),
                ],
                className="stats-card",
            )
            cards.append(buffered_card)

        return html.Div(cards, className="stats-container")

    @staticmethod
    def create_symbol_dropdown(
        available_symbols: List[str], default_symbol: str = "XBTUSD"
    ) -> dcc.Dropdown:
        """
        Create symbol selection dropdown

        Args:
            available_symbols: List of available symbols
            default_symbol: Default selected symbol

        Returns:
            Dash dropdown component
        """
        options = []
        for symbol in available_symbols:
            # Convert symbol to display label
            if symbol in ["XBTUSD", "BTC/USD"]:
                label = "BTC/USD"
                value = "BTC/USD"  # Use normalized format
            elif symbol in ["ETHUSD", "ETH/USD"]:
                label = "ETH/USD"
                value = "ETH/USD"  # Use normalized format
            elif symbol in ["SOLUSD", "SOL/USD"]:
                label = "SOL/USD"
                value = "SOL/USD"  # Use normalized format
            else:
                label = symbol
                value = symbol

            options.append({"label": label, "value": value})

        # Set default value intelligently
        if available_symbols:
            # Use the requested default if it's available, otherwise use first available
            if default_symbol in [opt["value"] for opt in options]:
                default_value = default_symbol
            else:
                default_value = options[0]["value"]
        else:
            # Fallback if no symbols available
            default_value = "BTC/USD"

        return dcc.Dropdown(
            id="symbol-dropdown",
            options=options,
            value=default_value,
            clearable=False,
            className="symbol-dropdown",
        )

    @staticmethod
    def create_chart_type_dropdown() -> dcc.Dropdown:
        """Create chart type selection dropdown"""
        return dcc.Dropdown(
            id="chart-type-dropdown",
            options=[
                {"label": "Candlestick", "value": "candlestick"},
                {"label": "Line Chart", "value": "line"},
                {"label": "OHLC", "value": "ohlc"},
            ],
            value="candlestick",
            clearable=False,
            className="chart-type-dropdown",
        )

    @staticmethod
    def create_interval_selector() -> dcc.Dropdown:
        """Create time interval selector"""
        return dcc.Dropdown(
            id="interval-dropdown",
            options=[
                {"label": "15 minutes", "value": 15},
                {"label": "1 hour", "value": 60},
                {"label": "4 hours", "value": 240},
                {"label": "1 day", "value": 1440},
            ],
            value=15,
            clearable=False,
            className="interval-dropdown",
        )

    @staticmethod
    def _empty_figure(title: str, message: str) -> Dict[str, Any]:
        """Create an empty figure with a message"""
        fig = go.Figure()
        fig.add_annotation(
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            text=message,
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        fig.update_layout(
            title=title,
            template="plotly_dark",
            height=400,
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, showticklabels=False),
        )
        return fig

    @staticmethod
    def _optimize_data_for_chart(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Optimize data for chart rendering by implementing smart decimation

        Args:
            data: Raw OHLC data list

        Returns:
            Optimized data list for better chart performance
        """
        if not data:
            return data

        data_length = len(data)

        # No optimization needed for small datasets
        if data_length <= 10000:
            return data

        # For large datasets, implement smart decimation
        # Keep recent data at full resolution, decimate older data
        if data_length <= 50000:
            # Light decimation: keep every other point for older data
            recent_data = data[-5000:]  # Keep last 5000 points at full resolution
            older_data = data[:-5000:2]  # Keep every 2nd point for older data
            return older_data + recent_data

        elif data_length <= 100000:
            # Medium decimation
            recent_data = data[-10000:]  # Keep last 10k points at full resolution
            mid_data = data[-50000:-10000:2]  # Keep every 2nd point for mid-range
            older_data = data[:-50000:5]  # Keep every 5th point for oldest data
            return older_data + mid_data + recent_data

        else:
            # Heavy decimation for very large datasets
            recent_data = data[-10000:]  # Keep last 10k points at full resolution
            mid_data = data[-50000:-10000:3]  # Keep every 3rd point for mid-range
            older_data = data[:-50000:10]  # Keep every 10th point for oldest data
            return older_data + mid_data + recent_data
