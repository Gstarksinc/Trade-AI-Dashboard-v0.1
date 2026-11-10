"""Correlation clusters: Dynamic empirical returns correlation with static fallback."""

import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy import text
from libs.database.connection import engine

log = logging.getLogger("risk-service.correlation-clusters")

# Static fallback cluster definition
STATIC_CLUSTERS: Dict[str, List[str]] = {
    "majors": ["BTCUSDT", "ETHUSDT"],
    "l1_platform": ["SOLUSDT", "BNBUSDT"],
    "high_beta_alt": ["XRPUSDT", "DOGEUSDT", "LINKUSDT", "TRXUSDT"],
}

STATIC_SYMBOL_MAP: Dict[str, str] = {}
for cluster_name, sym_list in STATIC_CLUSTERS.items():
    for sym in sym_list:
        STATIC_SYMBOL_MAP[sym] = cluster_name


class CorrelationClusterManager:
    def __init__(self):
        self.dynamic_clusters: Dict[str, str] = {}
        self.last_computed_at: Optional[float] = None

    async def compute_dynamic_clusters(self, lookback_days: int = 30) -> Dict[str, str]:
        """Calculates rolling correlation matrix of daily returns from TimescaleDB and clusters pairs."""
        try:
            query = text("""
                SELECT symbol, date_trunc('day', open_time) AS day, close
                FROM market_data.candles
                WHERE timeframe = '1h' AND open_time >= now() - INTERVAL '30 days'
                ORDER BY open_time ASC;
            """)
            async with engine.connect() as conn:
                res = await conn.execute(query)
                rows = res.fetchall()

            if len(rows) < 100:
                return STATIC_SYMBOL_MAP

            df = pd.DataFrame(rows, columns=["symbol", "day", "close"])
            pivoted = df.pivot_table(index="day", columns="symbol", values="close").pct_change().dropna()

            if pivoted.shape[1] < 2:
                return STATIC_SYMBOL_MAP

            corr_matrix = pivoted.corr()

            # Hierarchical clustering / greedy grouping for pairs with corr > 0.70
            groups = {}
            visited = set()
            cluster_id = 1

            for sym in corr_matrix.columns:
                if sym in visited:
                    continue
                correlated = corr_matrix[sym][corr_matrix[sym] >= 0.70].index.tolist()
                c_name = f"corr_cluster_{cluster_id}"
                for s in correlated:
                    groups[s] = c_name
                    visited.add(s)
                cluster_id += 1

            self.dynamic_clusters = groups
            return groups
        except Exception as e:
            log.warning("Dynamic correlation calculation failed, falling back to static clusters: %s", e)
            return STATIC_SYMBOL_MAP

    def get_cluster(self, symbol: str) -> str:
        sym_clean = symbol.upper()
        if sym_clean in self.dynamic_clusters:
            return self.dynamic_clusters[sym_clean]
        return STATIC_SYMBOL_MAP.get(sym_clean, "default_cluster")


cluster_mgr = CorrelationClusterManager()


def get_cluster(symbol: str) -> str:
    return cluster_mgr.get_cluster(symbol)
