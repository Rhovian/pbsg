# Known Issues and Future Enhancements

## Data Integrity

### Gap Detection and Backfill (Priority: Medium)

**Issue**: The system currently does not detect or fill gaps in OHLC data that may occur during:
- Network disconnections
- Database outages
- Service restarts
- Extended reconnection periods

**Current State**:
- ✅ Robust reconnection with resubscription minimizes gap frequency
- ✅ Duplicate detection prevents data corruption
- ✅ Health monitoring provides visibility into when gaps likely occurred
- ❌ No tracking of last received timestamps per symbol
- ❌ No gap detection mechanism
- ❌ No backfill capability

**Impact**:
- Missing 15-minute candles could affect technical analysis accuracy
- Time series may have unexpected discontinuities
- Historical data completeness not guaranteed

**Root Cause**:
- Kraken WebSocket documentation is unclear on snapshot behavior
- No identified REST API source for reliable historical OHLC backfill
- Current focus on real-time streaming rather than historical completeness

**Potential Solution Path**:

1. **Phase 1: Gap Detection**
   ```python
   class GapTracker:
       def __init__(self):
           self.last_seen = {}  # symbol -> last_timestamp

       def check_for_gaps(self, ohlc: OHLCData) -> List[datetime]:
           # Return list of missing 15-min intervals
           pass

       def record_received(self, ohlc: OHLCData):
           # Update last_seen tracker
           pass
   ```

2. **Phase 2: Data Source Research**
   - Research Kraken REST API for historical OHLC endpoints
   - Evaluate alternative APIs (CoinGecko, CoinMarketCap, etc.)
   - Compare data quality between sources
   - Assess rate limits and reliability

3. **Phase 3: Gap Filling Implementation**
   - REST API integration for backfill requests
   - Prioritization logic (recent gaps more critical)
   - Rate limiting and error handling
   - Backfill scheduling and retry mechanisms

**Workaround**:
- Monitor connection uptime statistics to identify when gaps likely occurred
- Log reconnection events as potential gap indicators
- Ensure system reliability to minimize gap frequency

**Example Gap Scenario**:
```
Timeline:
10:15 - Receive BTC/USD candle
10:20 - Network disconnection
10:35 - Reconnection established
10:45 - Receive BTC/USD candle

Gap: Missing 10:30 candle (15-minute interval)
```

**Related Files**:
- `src/services/data_sources/types.py` - OHLC data structures
- `src/services/data_sources/kraken.py` - WebSocket handler
- `src/services/data_sources/backpressure.py` - Health monitoring

---

## Monitoring and Observability

### Limited Production Monitoring (Priority: Medium)

**Issue**: The system lacks production-grade monitoring, metrics, and alerting capabilities essential for reliable operation.

**Current State**:
- ✅ Comprehensive structured logging with loguru
- ✅ Internal statistics tracking (connection health, storage performance, error rates)
- ✅ Health status reporting in application logs
- ❌ No Prometheus/metrics endpoints
- ❌ No external health check endpoints
- ❌ No alerting integration
- ❌ No real-time dashboards
- ❌ No SLA monitoring

**Impact**:
- Difficult to detect issues proactively in production
- No visibility into system performance trends
- Manual monitoring required for operational awareness
- Slower incident response times
- No historical performance baselines

**Potential Solution Path**:

1. **Phase 1: Metrics Integration**
   ```python
   from prometheus_client import Counter, Histogram, Gauge

   # Add metrics to IntegratedOHLCStorage
   ohlc_records_total = Counter('ohlc_records_received_total', 'Total OHLC records received', ['symbol', 'source'])
   storage_duration = Histogram('ohlc_storage_duration_seconds', 'Time spent storing OHLC data')
   connection_status = Gauge('websocket_connected', 'WebSocket connection status', ['exchange'])
   ```

2. **Phase 2: Health Check Endpoints**
   ```python
   # Add to main application
   @app.get("/health")
   async def health_check():
       return {
           "status": "healthy" if storage.is_healthy() else "unhealthy",
           "websocket_connected": handler.is_connected,
           "last_data_received": last_received_timestamp,
           "uptime_seconds": uptime
       }
   ```

3. **Phase 3: Alerting and Dashboards**
   - Grafana dashboards for key metrics
   - PagerDuty/Slack integration for critical alerts
   - SLA monitoring (99.9% uptime target)
   - Performance trending and capacity planning

**Key Metrics to Track**:
- **Throughput**: Records received per hour, storage operations per second
- **Latency**: WebSocket message processing time, database write latency
- **Reliability**: Connection uptime percentage, error rates by type
- **Data Quality**: Duplicate rate, gap detection events
- **Infrastructure**: Memory usage, CPU utilization, database connection pool

**Alerting Scenarios**:
- WebSocket disconnection > 60 seconds
- Storage health degraded
- Error rate > 5% over 10 minutes
- No data received for > 30 minutes
- Memory usage > 80%

**Related Files**:
- `src/services/data_sources/backpressure.py` - Health monitoring foundation
- `src/services/data_sources/integrated_storage.py` - Statistics collection

---

## Configuration

### Environment Variables Not Loaded (Priority: High)

**Issue**: The application does not currently load environment variables from the `.env` file, causing configuration issues and potential runtime failures.

**Current State**:
- ✅ `.env.example` file exists with proper template
- ✅ `python-dotenv` dependency installed
- ❌ No actual loading of `.env` file in application startup
- ❌ Configuration may fall back to defaults or fail

**Impact**:
- Database connections may fail if credentials not set in environment
- API keys and sensitive configuration not properly loaded
- Development environment setup incomplete
- Production deployments may require manual environment variable setup

**Root Cause**:
- Missing `load_dotenv()` call in application initialization
- Configuration module not importing environment variables properly

**Solution**:
```python
# Add to main.py or config/__init__.py
from dotenv import load_dotenv
load_dotenv()  # Load .env file before other imports
```

**Related Files**:
- `.env.example` - Environment variable template
- `src/config/settings.py` - Configuration management
- `main.py` - Application entry point

---

## Performance

### None Currently Identified

The current implementation demonstrates excellent performance characteristics:
- ✅ True bulk inserts (1000+ records/query)
- ✅ Memory-bounded operations
- ✅ Efficient duplicate detection
- ✅ Appropriate for 12 records/hour data volume

---

*Last Updated: 2024-01-15*