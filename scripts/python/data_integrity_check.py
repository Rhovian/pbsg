#!/usr/bin/env python3
"""
Data integrity checker for OHLC data
Detects gaps, duplicates, and other data quality issues
"""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from loguru import logger

load_dotenv()


@dataclass
class DataGap:
    """Represents a gap in the data"""
    symbol: str
    start_time: datetime
    end_time: datetime
    expected_intervals: int
    missing_intervals: int
    duration_hours: float

    @property
    def gap_percentage(self) -> float:
        """Percentage of missing data in this gap"""
        return (self.missing_intervals / self.expected_intervals) * 100


@dataclass
class DataIntegrityIssue:
    """Represents a data quality issue"""
    symbol: str
    timestamp: datetime
    issue_type: str
    description: str
    severity: str  # 'warning', 'error', 'critical'


@dataclass
class IntegrityReport:
    """Complete data integrity report"""
    symbol: str
    total_records: int
    date_range: Tuple[datetime, datetime]
    expected_records: int
    gaps: List[DataGap]
    issues: List[DataIntegrityIssue]
    completeness_percentage: float


class DataIntegrityChecker:
    """Checks OHLC data for integrity issues"""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "postgresql://pbsg:pbsg_password@localhost:5432/pbsg"
        )
        self.engine = create_engine(self.database_url)
        self.interval_minutes = 15  # 15-minute intervals

        # Supported symbols and their tables
        self.symbols = {
            "BTC/USD": "btc_ohlc",
            "ETH/USD": "eth_ohlc",
            "SOL/USD": "sol_ohlc"
        }

    def check_all_symbols(self) -> Dict[str, IntegrityReport]:
        """Check data integrity for all symbols"""
        reports = {}

        logger.info("Starting data integrity check for all symbols...")

        for symbol, table_name in self.symbols.items():
            logger.info(f"Checking {symbol}...")
            try:
                report = self.check_symbol_integrity(symbol, table_name)
                reports[symbol] = report
                logger.info(f"✅ {symbol} check complete")
            except Exception as e:
                logger.error(f"❌ Failed to check {symbol}: {e}")
                continue

        return reports

    def check_symbol_integrity(self, symbol: str, table_name: str) -> IntegrityReport:
        """Check data integrity for a specific symbol"""
        with Session(self.engine) as session:
            # Get basic stats
            total_records = self._get_record_count(session, table_name, symbol)
            date_range = self._get_date_range(session, table_name, symbol)

            if total_records == 0:
                return IntegrityReport(
                    symbol=symbol,
                    total_records=0,
                    date_range=(datetime.now(timezone.utc), datetime.now(timezone.utc)),
                    expected_records=0,
                    gaps=[],
                    issues=[],
                    completeness_percentage=0.0
                )

            # Calculate expected records based on date range
            expected_records = self._calculate_expected_records(date_range)

            # Find gaps in time series
            gaps = self._find_data_gaps(session, table_name, symbol, date_range)

            # Find other data quality issues
            issues = self._find_data_quality_issues(session, table_name, symbol)

            # Calculate completeness percentage
            completeness = (total_records / expected_records) * 100 if expected_records > 0 else 0

            return IntegrityReport(
                symbol=symbol,
                total_records=total_records,
                date_range=date_range,
                expected_records=expected_records,
                gaps=gaps,
                issues=issues,
                completeness_percentage=completeness
            )

    def _get_record_count(self, session: Session, table_name: str, symbol: str) -> int:
        """Get total record count for symbol"""
        query = text(f"""
            SELECT COUNT(*) as total
            FROM {table_name}
            WHERE symbol = :symbol
            AND timeframe = '15m'
        """)

        result = session.execute(query, {"symbol": symbol})
        return result.fetchone().total

    def _get_date_range(self, session: Session, table_name: str, symbol: str) -> Tuple[datetime, datetime]:
        """Get the date range of available data"""
        query = text(f"""
            SELECT
                MIN(time) as start_date,
                MAX(time) as end_date
            FROM {table_name}
            WHERE symbol = :symbol
            AND timeframe = '15m'
        """)

        result = session.execute(query, {"symbol": symbol})
        row = result.fetchone()
        return (row.start_date, row.end_date)

    def _calculate_expected_records(self, date_range: Tuple[datetime, datetime]) -> int:
        """Calculate expected number of 15-minute intervals"""
        start_date, end_date = date_range
        total_minutes = (end_date - start_date).total_seconds() / 60
        return int(total_minutes / self.interval_minutes) + 1

    def _find_data_gaps(self, session: Session, table_name: str, symbol: str,
                       date_range: Tuple[datetime, datetime]) -> List[DataGap]:
        """Find gaps in the time series data"""
        query = text(f"""
            WITH time_series AS (
                SELECT
                    time,
                    LAG(time) OVER (ORDER BY time) as prev_time
                FROM {table_name}
                WHERE symbol = :symbol
                AND timeframe = '15m'
                ORDER BY time
            ),
            gaps AS (
                SELECT
                    prev_time as gap_start,
                    time as gap_end,
                    EXTRACT(EPOCH FROM (time - prev_time))/60 as gap_minutes
                FROM time_series
                WHERE prev_time IS NOT NULL
                AND time - prev_time > INTERVAL '{self.interval_minutes} minutes'
            )
            SELECT
                gap_start,
                gap_end,
                gap_minutes
            FROM gaps
            ORDER BY gap_start
        """)

        result = session.execute(query, {"symbol": symbol})
        gaps = []

        for row in result:
            gap_minutes = row.gap_minutes
            missing_intervals = int(gap_minutes / self.interval_minutes) - 1
            expected_intervals = int(gap_minutes / self.interval_minutes)

            if missing_intervals > 0:
                gap = DataGap(
                    symbol=symbol,
                    start_time=row.gap_start,
                    end_time=row.gap_end,
                    expected_intervals=expected_intervals,
                    missing_intervals=missing_intervals,
                    duration_hours=gap_minutes / 60
                )
                gaps.append(gap)

        return gaps

    def _find_data_quality_issues(self, session: Session, table_name: str, symbol: str) -> List[DataIntegrityIssue]:
        """Find data quality issues like invalid OHLC relationships"""
        issues = []

        # Check for invalid OHLC relationships
        query = text(f"""
            SELECT time, open, high, low, close, volume
            FROM {table_name}
            WHERE symbol = :symbol
            AND timeframe = '15m'
            AND (
                high < low OR                    -- High should be >= Low
                high < open OR                   -- High should be >= Open
                high < close OR                  -- High should be >= Close
                low > open OR                    -- Low should be <= Open
                low > close OR                   -- Low should be <= Close
                open <= 0 OR                     -- Prices should be positive
                high <= 0 OR
                low <= 0 OR
                close <= 0 OR
                volume < 0                       -- Volume should be non-negative
            )
            ORDER BY time
        """)

        result = session.execute(query, {"symbol": symbol})

        for row in result:
            issue_desc = []

            if row.high < row.low:
                issue_desc.append(f"High ({row.high}) < Low ({row.low})")
            if row.high < row.open:
                issue_desc.append(f"High ({row.high}) < Open ({row.open})")
            if row.high < row.close:
                issue_desc.append(f"High ({row.high}) < Close ({row.close})")
            if row.low > row.open:
                issue_desc.append(f"Low ({row.low}) > Open ({row.open})")
            if row.low > row.close:
                issue_desc.append(f"Low ({row.low}) > Close ({row.close})")
            if row.open <= 0:
                issue_desc.append(f"Open price is non-positive ({row.open})")
            if row.high <= 0:
                issue_desc.append(f"High price is non-positive ({row.high})")
            if row.low <= 0:
                issue_desc.append(f"Low price is non-positive ({row.low})")
            if row.close <= 0:
                issue_desc.append(f"Close price is non-positive ({row.close})")
            if row.volume < 0:
                issue_desc.append(f"Volume is negative ({row.volume})")

            if issue_desc:
                issues.append(DataIntegrityIssue(
                    symbol=symbol,
                    timestamp=row.time,
                    issue_type="invalid_ohlc",
                    description="; ".join(issue_desc),
                    severity="error"
                ))

        # Check for duplicate timestamps
        dup_query = text(f"""
            SELECT time, COUNT(*) as count
            FROM {table_name}
            WHERE symbol = :symbol
            AND timeframe = '15m'
            GROUP BY time
            HAVING COUNT(*) > 1
            ORDER BY time
        """)

        dup_result = session.execute(dup_query, {"symbol": symbol})

        for row in dup_result:
            issues.append(DataIntegrityIssue(
                symbol=symbol,
                timestamp=row.time,
                issue_type="duplicate_timestamp",
                description=f"Duplicate timestamp found ({row.count} records)",
                severity="warning"
            ))

        return issues

    def print_report(self, reports: Dict[str, IntegrityReport]) -> None:
        """Print a formatted integrity report"""
        print("\n" + "="*80)
        print("📊 DATA INTEGRITY REPORT")
        print("="*80)

        for symbol, report in reports.items():
            print(f"\n🔍 {symbol}")
            print("-" * 40)

            if report.total_records == 0:
                print("❌ No data found")
                continue

            # Basic stats
            start_date = report.date_range[0].strftime("%Y-%m-%d %H:%M")
            end_date = report.date_range[1].strftime("%Y-%m-%d %H:%M")

            print(f"📈 Records: {report.total_records:,} / {report.expected_records:,} expected")
            print(f"📅 Date Range: {start_date} → {end_date}")
            print(f"✅ Completeness: {report.completeness_percentage:.1f}%")

            # Gaps
            if report.gaps:
                print(f"\n⚠️  Found {len(report.gaps)} data gaps:")
                total_missing = sum(gap.missing_intervals for gap in report.gaps)
                print(f"   Total missing intervals: {total_missing:,}")

                for i, gap in enumerate(report.gaps[:5], 1):  # Show first 5 gaps
                    gap_start = gap.start_time.strftime("%Y-%m-%d %H:%M")
                    gap_end = gap.end_time.strftime("%Y-%m-%d %H:%M")
                    print(f"   {i}. {gap_start} → {gap_end}")
                    print(f"      Missing: {gap.missing_intervals} intervals ({gap.duration_hours:.1f}h)")

                if len(report.gaps) > 5:
                    print(f"   ... and {len(report.gaps) - 5} more gaps")
            else:
                print("\n✅ No data gaps found")

            # Data quality issues
            if report.issues:
                print(f"\n🚨 Found {len(report.issues)} data quality issues:")

                # Group by issue type
                issue_types = {}
                for issue in report.issues:
                    if issue.issue_type not in issue_types:
                        issue_types[issue.issue_type] = []
                    issue_types[issue.issue_type].append(issue)

                for issue_type, issues in issue_types.items():
                    print(f"   {issue_type}: {len(issues)} occurrences")

                    # Show first few examples
                    for issue in issues[:3]:
                        timestamp = issue.timestamp.strftime("%Y-%m-%d %H:%M")
                        print(f"     • {timestamp}: {issue.description}")

                    if len(issues) > 3:
                        print(f"     ... and {len(issues) - 3} more")
            else:
                print("\n✅ No data quality issues found")

        print("\n" + "="*80)
        print("✅ Integrity check complete")


def main():
    """Run the data integrity check"""
    checker = DataIntegrityChecker()

    try:
        reports = checker.check_all_symbols()
        checker.print_report(reports)

        # Return exit code based on findings
        total_issues = sum(len(report.issues) for report in reports.values())
        total_gaps = sum(len(report.gaps) for report in reports.values())

        if total_issues > 0 or total_gaps > 0:
            logger.warning(f"Found {total_gaps} gaps and {total_issues} data quality issues")
            return 1
        else:
            logger.info("All data integrity checks passed")
            return 0

    except Exception as e:
        logger.error(f"Data integrity check failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())