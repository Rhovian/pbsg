"""Dash web framework service for creating interactive dashboards"""

import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objs as go
import plotly.express as px
from typing import Dict, List, Optional, Any
from loguru import logger


class DashService:
    """Service for creating and managing Dash web applications"""

    def __init__(self, debug: bool = False) -> None:
        self.app = dash.Dash(__name__)
        self.debug = debug
        self._setup_layout()
        self._setup_callbacks()

    def _setup_layout(self) -> None:
        """Setup the basic layout for the Dash application"""
        self.app.layout = html.Div([
            html.H1("PBSG Dashboard", style={'textAlign': 'center'}),

            html.Div([
                html.Label("Select Symbol:"),
                dcc.Dropdown(
                    id='symbol-dropdown',
                    options=[
                        {'label': 'BTC/USD', 'value': 'XBTUSD'},
                        {'label': 'ETH/USD', 'value': 'ETHUSD'},
                    ],
                    value='XBTUSD'
                )
            ], style={'width': '30%', 'display': 'inline-block'}),

            html.Div([
                dcc.Graph(id='price-chart')
            ]),

            html.Div([
                dcc.Graph(id='volume-chart')
            ]),

            dcc.Interval(
                id='interval-component',
                interval=5*1000,  # Update every 5 seconds
                n_intervals=0
            )
        ])

    def _setup_callbacks(self) -> None:
        """Setup Dash callbacks for interactivity"""

        @self.app.callback(
            Output('price-chart', 'figure'),
            Input('symbol-dropdown', 'value'),
            Input('interval-component', 'n_intervals')
        )
        def update_price_chart(selected_symbol: str, n: int) -> Dict[str, Any]:
            """Update the price chart based on selected symbol"""
            logger.debug(f"Updating price chart for {selected_symbol}")

            # TODO: Replace with actual data from database/cache
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=[],
                y=[],
                mode='lines',
                name='Price'
            ))

            fig.update_layout(
                title=f'{selected_symbol} Price Chart',
                xaxis_title='Time',
                yaxis_title='Price (USD)'
            )

            return fig

        @self.app.callback(
            Output('volume-chart', 'figure'),
            Input('symbol-dropdown', 'value'),
            Input('interval-component', 'n_intervals')
        )
        def update_volume_chart(selected_symbol: str, n: int) -> Dict[str, Any]:
            """Update the volume chart based on selected symbol"""
            logger.debug(f"Updating volume chart for {selected_symbol}")

            # TODO: Replace with actual data from database/cache
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[],
                y=[],
                name='Volume'
            ))

            fig.update_layout(
                title=f'{selected_symbol} Volume Chart',
                xaxis_title='Time',
                yaxis_title='Volume'
            )

            return fig

    def run(self, host: str = '127.0.0.1', port: int = 8050) -> None:
        """Run the Dash application"""
        logger.info(f"Starting Dash server on {host}:{port}")
        self.app.run(debug=self.debug, host=host, port=port)

    def get_app(self) -> dash.Dash:
        """Get the Dash application instance"""
        return self.app