"""
Data Science Agent - Phase 28
Data analysis, visualization, statistical modeling, ML.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import hashlib
import pickle
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict, Counter
from enum import Enum
import numpy as np

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, accuracy_score, classification_report
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import scipy.stats as stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

DB_DIR = "database"
DS_DB = os.path.join(DB_DIR, "data_science.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_ds_connection():
    import sqlite3
    conn = sqlite3.connect(DS_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_ds_db():
    conn = get_ds_connection()
    cursor = conn.cursor()

    # Datasets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            source_type TEXT,           -- csv, json, parquet, sql, api, manual
            source_path TEXT,
            rows INTEGER DEFAULT 0,
            columns INTEGER DEFAULT 0,
            column_info TEXT,           -- JSON: name, dtype, stats
            size_bytes INTEGER,
            checksum TEXT,
            tags TEXT,                  -- JSON array
            is_active BOOLEAN DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Data snapshots (versioned data)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_snapshots (
            id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            description TEXT,
            rows INTEGER,
            columns INTEGER,
            checksum TEXT,
            storage_path TEXT,          -- pickled dataframe or parquet
            created_at REAL NOT NULL,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id)
        )
    """)

    # Analyses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            name TEXT NOT NULL,
            analysis_type TEXT,         -- eda, statistical, ml, viz, custom
            description TEXT,
            code TEXT,                  -- Python code used
            results TEXT,               -- JSON results
            figures TEXT,               -- JSON: figure paths
            status TEXT DEFAULT 'completed',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id)
        )
    """)

    # Models
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id TEXT PRIMARY KEY,
            dataset_id TEXT,
            analysis_id TEXT,
            name TEXT NOT NULL,
            model_type TEXT,            -- regression, classification, clustering, etc.
            algorithm TEXT,             -- linear_regression, random_forest, kmeans, etc.
            target_column TEXT,
            features TEXT,              -- JSON array
            hyperparameters TEXT,       -- JSON
            metrics TEXT,               -- JSON: rmse, accuracy, etc.
            model_path TEXT,            -- pickled model
            feature_importance TEXT,    -- JSON
            training_time REAL,
            is_deployed BOOLEAN DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id)
        )
    """)

    # Predictions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            input_data TEXT,            -- JSON
            prediction REAL,
            probability REAL,           -- for classification
            input_hash TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (model_id) REFERENCES models(id)
        )
    """)

    # Visualizations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visualizations (
            id TEXT PRIMARY KEY,
            analysis_id TEXT,
            dataset_id TEXT,
            name TEXT NOT NULL,
            viz_type TEXT,              -- histogram, scatter, box, heatmap, line, bar, etc.
            config TEXT,                -- JSON: columns, aesthetics, etc.
            figure_path TEXT,
            thumbnail_path TEXT,
            description TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        )
    """)

    # Notebooks/Workflows
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            steps TEXT,                 -- JSON array of steps
            dataset_ids TEXT,           -- JSON array
            status TEXT DEFAULT 'draft',
            schedule TEXT,              -- cron expression for automation
            last_run REAL,
            next_run REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Statistical tests
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS statistical_tests (
            id TEXT PRIMARY KEY,
            analysis_id TEXT,
            test_name TEXT NOT NULL,    -- t_test, chi2, anova, mannwhitney, etc.
            hypothesis TEXT,
            variables TEXT,             -- JSON
            test_statistic REAL,
            p_value REAL,
            degrees_freedom REAL,
            effect_size REAL,
            conclusion TEXT,            -- reject/fail_to_reject
            alpha REAL DEFAULT 0.05,
            created_at REAL NOT NULL,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        )
    """)

    conn.commit()
    conn.close()


init_ds_db()


@dataclass
class Dataset:
    id: str
    name: str
    description: str
    source_type: str
    source_path: str
    rows: int
    columns: int
    column_info: Dict
    size_bytes: int
    checksum: str
    tags: List[str]
    is_active: bool
    created_at: float
    updated_at: float


class DatasetManager:
    def __init__(self):
        pass

    def load_csv(self, file_path: str, name: str = None, description: str = "",
                 **kwargs) -> str:
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required for CSV loading. pip install pandas")
        
        df = pd.read_csv(file_path, **kwargs)
        return self._register_dataset(df, name or os.path.basename(file_path),
                                      description, "csv", file_path)

    def load_json(self, file_path: str, name: str = None, description: str = "",
                  **kwargs) -> str:
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required for JSON loading. pip install pandas")
        
        df = pd.read_json(file_path, **kwargs)
        return self._register_dataset(df, name or os.path.basename(file_path),
                                      description, "json", file_path)

    def load_parquet(self, file_path: str, name: str = None, description: str = "") -> str:
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required for Parquet loading. pip install pandas pyarrow")
        
        df = pd.read_parquet(file_path)
        return self._register_dataset(df, name or os.path.basename(file_path),
                                      description, "parquet", file_path)

    def create_from_dict(self, data: Dict, name: str, description: str = "") -> str:
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        df = pd.DataFrame(data)
        return self._register_dataset(df, name, description, "manual", "")

    def create_from_records(self, records: List[Dict], name: str, description: str = "") -> str:
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        df = pd.DataFrame.from_records(records)
        return self._register_dataset(df, name, description, "manual", "")

    def _register_dataset(self, df, name: str, description: str,
                          source_type: str, source_path: str) -> str:
        dataset_id = f"ds_{int(time.time() * 1000) % 100000000:08d}"
        
        # Compute column info
        column_info = {}
        for col in df.columns:
            dtype = str(df[col].dtype)
            col_info = {"name": col, "dtype": dtype}
            
            if pd.api.types.is_numeric_dtype(df[col]):
                col_info.update({
                    "min": float(df[col].min()) if not df[col].isna().all() else None,
                    "max": float(df[col].max()) if not df[col].isna().all() else None,
                    "mean": float(df[col].mean()) if not df[col].isna().all() else None,
                    "std": float(df[col].std()) if not df[col].isna().all() else None,
                    "median": float(df[col].median()) if not df[col].isna().all() else None,
                    "null_count": int(df[col].isna().sum()),
                    "unique_count": int(df[col].nunique())
                })
            elif pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col]):
                col_info.update({
                    "null_count": int(df[col].isna().sum()),
                    "unique_count": int(df[col].nunique()),
                    "top_values": df[col].value_counts().head(5).to_dict()
                })
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                col_info.update({
                    "min": str(df[col].min()) if not df[col].isna().all() else None,
                    "max": str(df[col].max()) if not df[col].isna().all() else None,
                    "null_count": int(df[col].isna().sum())
                })
            
            column_info[col] = col_info
        
        # Checksum
        checksum = hashlib.md5(pd.util.hash_pandas_object(df).values).hexdigest()
        
        # Save to parquet for efficient storage
        storage_path = os.path.join(DB_DIR, f"{dataset_id}.parquet")
        df.to_parquet(storage_path, index=False)
        size_bytes = os.path.getsize(storage_path)
        
        conn = get_ds_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO datasets (id, name, description, source_type, source_path,
                                 rows, columns, column_info, size_bytes, checksum,
                                 tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (dataset_id, name, description, source_type, source_path,
              len(df), len(df.columns), json.dumps(column_info), size_bytes, checksum,
              json.dumps([]), time.time(), time.time()))
        
        # Create initial snapshot
        snapshot_id = f"snap_{int(time.time() * 1000) % 100000000:08d}"
        cursor.execute("""
            INSERT INTO data_snapshots (id, dataset_id, version, description,
                                       rows, columns, checksum, storage_path, created_at)
            VALUES (?, ?, 1, 'Initial version', ?, ?, ?, ?, ?)
        """, (snapshot_id, dataset_id, len(df), len(df.columns), checksum,
              storage_path, time.time()))
        
        conn.commit()
        conn.close()
        return dataset_id

    def get_dataset(self, dataset_id: str) -> Optional[Dict]:
        conn = get_ds_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "description": row[2],
                "source_type": row[3], "source_path": row[4],
                "rows": row[5], "columns": row[6],
                "column_info": json.loads(row[7]) if row[7] else {},
                "size_bytes": row[8], "checksum": row[9],
                "tags": json.loads(row[10]) if row[10] else [],
                "is_active": row[11], "created_at": row[12], "updated_at": row[13]
            }
        return None

    def load_dataframe(self, dataset_id: str):
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            return None
        
        storage_path = os.path.join(DB_DIR, f"{dataset_id}.parquet")
        if os.path.exists(storage_path):
            return pd.read_parquet(storage_path)
        
        # Fallback to latest snapshot
        conn = get_ds_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT storage_path FROM data_snapshots 
            WHERE dataset_id = ? ORDER BY version DESC LIMIT 1
        """, (dataset_id,))
        row = cursor.fetchone()
        conn.close()
        if row and os.path.exists(row[0]):
            return pd.read_parquet(row[0])
        
        return None

    def list_datasets(self, tags: List[str] = None) -> List[Dict]:
        conn = get_ds_connection()
        cursor = conn.cursor()
        if tags:
            # Simple tag filtering
            cursor.execute("SELECT * FROM datasets WHERE is_active = 1 ORDER BY created_at DESC")
        else:
            cursor.execute("SELECT * FROM datasets WHERE is_active = 1 ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for r in rows:
            dataset_tags = json.loads(r[10]) if r[10] else []
            if tags and not any(t in dataset_tags for t in tags):
                continue
            results.append({
                "id": r[0], "name": r[1], "description": r[2],
                "source_type": r[3], "rows": r[5], "columns": r[6],
                "tags": dataset_tags, "created_at": r[12]
            })
        return results

    def delete_dataset(self, dataset_id: str) -> bool:
        conn = get_ds_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE datasets SET is_active = 0 WHERE id = ?", (dataset_id,))
        conn.commit()
        conn.close()
        
        # Clean up parquet file
        storage_path = os.path.join(DB_DIR, f"{dataset_id}.parquet")
        if os.path.exists(storage_path):
            os.remove(storage_path)
        return True


class EDAEngine:
    @staticmethod
    def run_eda(dataset_id: str, name: str = "EDA") -> Dict:
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        results = {
            "dataset_id": dataset_id,
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
            "missing_percentage": (df.isnull().sum() / len(df) * 100).to_dict(),
            "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
        }
        
        # Numeric summary
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            results["numeric_summary"] = df[numeric_cols].describe().to_dict()
            results["correlations"] = df[numeric_cols].corr().to_dict()
            results["skewness"] = df[numeric_cols].skew().to_dict()
            results["kurtosis"] = df[numeric_cols].kurtosis().to_dict()
        
        # Categorical summary
        cat_cols = df.select_dtypes(include=['object', 'category']).columns
        if len(cat_cols) > 0:
            results["categorical_summary"] = {}
            for col in cat_cols:
                vc = df[col].value_counts()
                results["categorical_summary"][col] = {
                    "unique_count": int(df[col].nunique()),
                    "top_10": vc.head(10).to_dict(),
                    "top_10_percentage": (vc.head(10) / len(df) * 100).to_dict()
                }
        
        # Date columns
        date_cols = df.select_dtypes(include=['datetime64']).columns
        if len(date_cols) > 0:
            results["datetime_summary"] = {}
            for col in date_cols:
                results["datetime_summary"][col] = {
                    "min": str(df[col].min()),
                    "max": str(df[col].max()),
                    "range_days": (df[col].max() - df[col].min()).days
                }
        
        # Outlier detection (IQR method)
        results["outliers"] = {}
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            outliers = df[(df[col] < lower) | (df[col] > upper)]
            results["outliers"][col] = {
                "count": len(outliers),
                "percentage": len(outliers) / len(df) * 100,
                "lower_bound": float(lower),
                "upper_bound": float(upper)
            }
        
        # Duplicate rows
        results["duplicate_rows"] = int(df.duplicated().sum())
        
        return results

    @staticmethod
    def correlation_analysis(dataset_id: str, method: str = "pearson",
                              target: str = None) -> Dict:
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.empty:
            return {"error": "No numeric columns"}
        
        corr_matrix = numeric_df.corr(method=method)
        
        results = {
            "method": method,
            "correlation_matrix": corr_matrix.to_dict(),
            "high_correlations": []
        }
        
        # Find high correlations (>0.7 or <-0.7)
        for i, col1 in enumerate(corr_matrix.columns):
            for col2 in corr_matrix.columns[i+1:]:
                val = corr_matrix.loc[col1, col2]
                if abs(val) > 0.7:
                    results["high_correlations"].append({
                        "var1": col1, "var2": col2, "correlation": float(val)
                    })
        
        # Target correlations
        if target and target in corr_matrix.columns:
            results["target_correlations"] = corr_matrix[target].drop(target).sort_values(
                key=abs, ascending=False
            ).to_dict()
        
        return results


class StatisticalTestEngine:
    @staticmethod
    def t_test_1sample(dataset_id: str, column: str, popmean: float) -> Dict:
        if not SCIPY_AVAILABLE:
            raise ImportError("scipy required. pip install scipy")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        data = df[column].dropna()
        stat, p = stats.ttest_1samp(data, popmean)
        
        return {
            "test": "one_sample_t_test",
            "column": column,
            "popmean": popmean,
            "sample_mean": float(data.mean()),
            "sample_std": float(data.std()),
            "n": len(data),
            "t_statistic": float(stat),
            "p_value": float(p),
            "conclusion": "reject" if p < 0.05 else "fail_to_reject"
        }

    @staticmethod
    def t_test_2sample(dataset_id: str, column: str, group_column: str,
                        group1: Any, group2: Any, equal_var: bool = False) -> Dict:
        if not SCIPY_AVAILABLE:
            raise ImportError("scipy required. pip install scipy")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        g1_data = df[df[group_column] == group1][column].dropna()
        g2_data = df[df[group_column] == group2][column].dropna()
        
        stat, p = stats.ttest_ind(g1_data, g2_data, equal_var=equal_var)
        
        return {
            "test": "two_sample_t_test",
            "column": column,
            "group_column": group_column,
            "group1": str(group1), "group2": str(group2),
            "group1_mean": float(g1_data.mean()), "group2_mean": float(g2_data.mean()),
            "group1_std": float(g1_data.std()), "group2_std": float(g2_data.std()),
            "group1_n": len(g1_data), "group2_n": len(g2_data),
            "t_statistic": float(stat), "p_value": float(p),
            "equal_var": equal_var,
            "conclusion": "reject" if p < 0.05 else "fail_to_reject"
        }

    @staticmethod
    def chi2_test(dataset_id: str, col1: str, col2: str) -> Dict:
        if not SCIPY_AVAILABLE:
            raise ImportError("scipy required. pip install scipy")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        contingency = pd.crosstab(df[col1], df[col2])
        chi2, p, dof, expected = stats.chi2_contingency(contingency)
        
        return {
            "test": "chi2_independence",
            "column1": col1, "column2": col2,
            "contingency_table": contingency.to_dict(),
            "chi2_statistic": float(chi2),
            "p_value": float(p),
            "degrees_freedom": int(dof),
            "conclusion": "reject" if p < 0.05 else "fail_to_reject"
        }

    @staticmethod
    def anova_test(dataset_id: str, value_column: str, group_column: str) -> Dict:
        if not SCIPY_AVAILABLE:
            raise ImportError("scipy required. pip install scipy")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        groups = [grp[value_column].dropna() for _, grp in df.groupby(group_column)]
        groups = [g for g in groups if len(g) > 0]
        
        if len(groups) < 2:
            return {"error": "Need at least 2 groups"}
        
        stat, p = stats.f_oneway(*groups)
        
        # Group statistics
        group_stats = {}
        for name, grp in df.groupby(group_column):
            vals = grp[value_column].dropna()
            group_stats[str(name)] = {
                "mean": float(vals.mean()), "std": float(vals.std()),
                "n": len(vals)
            }
        
        return {
            "test": "one_way_anova",
            "value_column": value_column, "group_column": group_column,
            "num_groups": len(groups),
            "group_stats": group_stats,
            "f_statistic": float(stat),
            "p_value": float(p),
            "conclusion": "reject" if p < 0.05 else "fail_to_reject"
        }

    @staticmethod
    def mannwhitney_test(dataset_id: str, column: str, group_column: str,
                          group1: Any, group2: Any) -> Dict:
        if not SCIPY_AVAILABLE:
            raise ImportError("scipy required. pip install scipy")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        g1_data = df[df[group_column] == group1][column].dropna()
        g2_data = df[df[group_column] == group2][column].dropna()
        
        stat, p = stats.mannwhitneyu(g1_data, g2_data, alternative='two-sided')
        
        return {
            "test": "mann_whitney_u",
            "column": column,
            "group_column": group_column,
            "group1": str(group1), "group2": str(group2),
            "group1_median": float(g1_data.median()), "group2_median": float(g2_data.median()),
            "u_statistic": float(stat), "p_value": float(p),
            "conclusion": "reject" if p < 0.05 else "fail_to_reject"
        }

    @staticmethod
    def normality_test(dataset_id: str, column: str) -> Dict:
        if not SCIPY_AVAILABLE:
            raise ImportError("scipy required. pip install scipy")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        data = df[column].dropna()
        
        # Shapiro-Wilk (for n < 5000)
        if len(data) <= 5000:
            stat, p = stats.shapiro(data)
            test = "shapiro_wilk"
        else:
            stat, p = stats.normaltest(data)
            test = "dagostino_pearson"
        
        return {
            "test": test, "column": column, "n": len(data),
            "statistic": float(stat), "p_value": float(p),
            "is_normal": p > 0.05,
            "conclusion": "normal" if p > 0.05 else "not_normal"
        }


class VisualizationEngine:
    def __init__(self):
        self.fig_dir = os.path.join(DB_DIR, "figures")
        os.makedirs(self.fig_dir, exist_ok=True)

    def _save_figure(self, fig, name: str) -> tuple:
        """Save figure and return paths."""
        timestamp = int(time.time())
        fig_path = os.path.join(self.fig_dir, f"{name}_{timestamp}.png")
        thumb_path = os.path.join(self.fig_dir, f"{name}_{timestamp}_thumb.png")
        
        fig.savefig(fig_path, dpi=150, bbox_inches='tight')
        fig.savefig(thumb_path, dpi=50, bbox_inches='tight')
        plt.close(fig)
        
        return fig_path, thumb_path

    def histogram(self, dataset_id: str, column: str, bins: int = 30,
                  kde: bool = False, title: str = None) -> Dict:
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib required. pip install matplotlib")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        fig, ax = plt.subplots(figsize=(10, 6))
        data = df[column].dropna()
        
        ax.hist(data, bins=bins, density=kde, alpha=0.7, edgecolor='black')
        
        if kde:
            from scipy.stats import gaussian_kde
            kde_func = gaussian_kde(data)
            x_range = np.linspace(data.min(), data.max(), 200)
            ax.plot(x_range, kde_func(x_range), 'r-', lw=2)
        
        ax.set_xlabel(column)
        ax.set_ylabel('Density' if kde else 'Frequency')
        ax.set_title(title or f'Histogram of {column}')
        ax.grid(True, alpha=0.3)
        
        fig_path, thumb_path = self._save_figure(fig, f"hist_{column}")
        
        return {
            "type": "histogram", "column": column,
            "figure_path": fig_path, "thumbnail_path": thumb_path,
            "config": {"bins": bins, "kde": kde}
        }

    def scatter(self, dataset_id: str, x_col: str, y_col: str,
                color_col: str = None, size_col: str = None,
                title: str = None) -> Dict:
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib required. pip install matplotlib")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        fig, ax = plt.subplots(figsize=(10, 6))
        data = df[[x_col, y_col]].dropna()
        
        # Prepare colors
        color_vals = None
        color_label = None
        if color_col and color_col in df.columns:
            colors = df.loc[data.index, color_col]
            # Handle categorical/string color columns
            dtype_str = str(colors.dtype)
            if (colors.dtype == 'object' or colors.dtype.name == 'category' 
                or dtype_str == 'string' or dtype_str == 'str'):
                color_vals = pd.Categorical(colors).codes
                color_label = color_col
                color_map = 'tab10'
            else:
                color_vals = colors.values
                color_label = color_col
                color_map = 'viridis'
        
        # Prepare sizes
        size_vals = None
        if size_col and size_col in df.columns:
            sizes = df.loc[data.index, size_col]
            size_vals = (sizes - sizes.min()) / (sizes.max() - sizes.min()) * 200 + 20
        
        # Single scatter call with all parameters
        scatter = ax.scatter(
            data[x_col], data[y_col],
            c=color_vals, cmap=color_map if color_vals is not None else None,
            s=size_vals, alpha=0.6
        )
        
        if color_vals is not None:
            if color_col and color_col in df.columns:
                colors = df.loc[data.index, color_col]
                dtype_str = str(colors.dtype)
                if (colors.dtype == 'object' or colors.dtype.name == 'category' 
                    or dtype_str == 'string' or dtype_str == 'str'):
                    categories = pd.Categorical(colors).categories
                    cbar = plt.colorbar(scatter, ax=ax, label=color_col, ticks=range(len(categories)))
                    cbar.ax.set_yticklabels(categories)
                else:
                    plt.colorbar(scatter, ax=ax, label=color_label)
        
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title(title or f'{y_col} vs {x_col}')
        ax.grid(True, alpha=0.3)
        
        fig_path, thumb_path = self._save_figure(fig, f"scatter_{x_col}_{y_col}")
        
        return {
            "type": "scatter", "x": x_col, "y": y_col,
            "figure_path": fig_path, "thumbnail_path": thumb_path
        }

    def box_plot(self, dataset_id: str, column: str, group_column: str = None,
                 title: str = None) -> Dict:
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib required. pip install matplotlib")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if group_column:
            groups = [grp[column].dropna() for _, grp in df.groupby(group_column)]
            labels = [str(name) for name, _ in df.groupby(group_column)]
            ax.boxplot(groups, tick_labels=labels)
            ax.set_xlabel(group_column)
        else:
            ax.boxplot(df[column].dropna())
        
        ax.set_ylabel(column)
        ax.set_title(title or f'Box Plot of {column}' + (f' by {group_column}' if group_column else ''))
        ax.grid(True, alpha=0.3)
        
        fig_path, thumb_path = self._save_figure(fig, f"box_{column}")
        
        return {
            "type": "box_plot", "column": column, "group_by": group_column,
            "figure_path": fig_path, "thumbnail_path": thumb_path
        }

    def correlation_heatmap(self, dataset_id: str, method: str = "pearson",
                             title: str = None) -> Dict:
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib required. pip install matplotlib")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.empty:
            return {"error": "No numeric columns"}
        
        corr = numeric_df.corr(method=method)
        
        fig, ax = plt.subplots(figsize=(12, 10))
        im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
        
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=45, ha='right')
        ax.set_yticklabels(corr.columns)
        
        # Add correlation values
        for i in range(len(corr.columns)):
            for j in range(len(corr.columns)):
                text = ax.text(j, i, f'{corr.iloc[i, j]:.2f}',
                              ha='center', va='center', fontsize=8,
                              color='white' if abs(corr.iloc[i, j]) > 0.5 else 'black')
        
        plt.colorbar(im, ax=ax, label='Correlation')
        ax.set_title(title or f'Correlation Matrix ({method})')
        
        fig_path, thumb_path = self._save_figure(fig, f"heatmap_corr")
        
        return {
            "type": "heatmap", "method": method,
            "figure_path": fig_path, "thumbnail_path": thumb_path
        }

    def pair_plot(self, dataset_id: str, columns: List[str] = None,
                   hue: str = None, title: str = None) -> Dict:
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib required. pip install matplotlib")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()[:5]
        
        n = len(columns)
        fig, axes = plt.subplots(n, n, figsize=(3*n, 3*n))
        
        for i, col1 in enumerate(columns):
            for j, col2 in enumerate(columns):
                ax = axes[i, j]
                if i == j:
                    ax.hist(df[col1].dropna(), bins=20, alpha=0.7, edgecolor='black')
                    ax.set_ylabel(col1)
                else:
                    ax.scatter(df[col2], df[col1], alpha=0.5, s=10)
                    ax.set_xlabel(col2)
                    ax.set_ylabel(col1)
                ax.grid(True, alpha=0.3)
        
        fig.suptitle(title or 'Pair Plot', fontsize=16)
        plt.tight_layout()
        
        fig_path, thumb_path = self._save_figure(fig, "pair_plot")
        
        return {
            "type": "pair_plot", "columns": columns,
            "figure_path": fig_path, "thumbnail_path": thumb_path
        }

    def line_plot(self, dataset_id: str, x_col: str, y_cols: Union[str, List[str]],
                   title: str = None) -> Dict:
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib required. pip install matplotlib")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        if isinstance(y_cols, str):
            y_cols = [y_cols]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        x_data = df[x_col]
        for y_col in y_cols:
            ax.plot(x_data, df[y_col], label=y_col, marker='o', markersize=3)
        
        ax.set_xlabel(x_col)
        ax.set_ylabel('Value')
        ax.set_title(title or f'Line Plot: {", ".join(y_cols)} over {x_col}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        fig_path, thumb_path = self._save_figure(fig, f"line_{x_col}")
        
        return {
            "type": "line_plot", "x": x_col, "y": y_cols,
            "figure_path": fig_path, "thumbnail_path": thumb_path
        }

    def bar_plot(self, dataset_id: str, x_col: str, y_col: str,
                  aggfunc: str = 'mean', title: str = None) -> Dict:
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib required. pip install matplotlib")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if aggfunc == 'count':
            grouped = df[x_col].value_counts()
        else:
            grouped = df.groupby(x_col)[y_col].agg(aggfunc)
        
        grouped.sort_values(ascending=False).head(20).plot(kind='bar', ax=ax)
        ax.set_xlabel(x_col)
        ax.set_ylabel(f'{aggfunc}({y_col})' if aggfunc != 'count' else 'Count')
        ax.set_title(title or f'Bar Plot: {aggfunc} of {y_col} by {x_col}')
        ax.grid(True, alpha=0.3, axis='y')
        plt.xticks(rotation=45, ha='right')
        
        fig_path, thumb_path = self._save_figure(fig, f"bar_{x_col}_{y_col}")
        
        return {
            "type": "bar_plot", "x": x_col, "y": y_col, "aggfunc": aggfunc,
            "figure_path": fig_path, "thumbnail_path": thumb_path
        }


class MLEngine:
    def __init__(self):
        self.model_dir = os.path.join(DB_DIR, "models")
        os.makedirs(self.model_dir, exist_ok=True)

    def train_regression(self, dataset_id: str, target: str, features: List[str],
                         algorithm: str = "linear", test_size: float = 0.2,
                         random_state: int = 42, **kwargs) -> Dict:
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required. pip install scikit-learn")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        # Prepare data
        X = df[features].dropna()
        y = df.loc[X.index, target].dropna()
        X = X.loc[y.index]  # Align
        
        if len(X) < 10:
            return {"error": "Insufficient data after dropping NaN"}
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        
        # Scale
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train model
        if algorithm == "linear":
            model = LinearRegression()
        elif algorithm == "random_forest":
            model = RandomForestRegressor(n_estimators=100, random_state=random_state, **kwargs)
        else:
            return {"error": f"Unknown algorithm: {algorithm}"}
        
        model.fit(X_train_scaled, y_train)
        
        # Predict
        y_pred_train = model.predict(X_train_scaled)
        y_pred_test = model.predict(X_test_scaled)
        
        # Metrics
        train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
        test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
        train_r2 = model.score(X_train_scaled, y_train)
        test_r2 = model.score(X_test_scaled, y_test)
        
        # Feature importance
        if hasattr(model, 'feature_importances_'):
            importance = dict(zip(features, model.feature_importances_))
        elif hasattr(model, 'coef_'):
            importance = dict(zip(features, model.coef_))
        else:
            importance = {}
        
        # Save model
        model_id = f"model_{int(time.time() * 1000) % 100000000:08d}"
        model_path = os.path.join(self.model_dir, f"{model_id}.pkl")
        
        model_data = {
            "model": model, "scaler": scaler, "features": features,
            "target": target, "algorithm": algorithm
        }
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        # Register in DB
        conn = get_ds_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO models (id, dataset_id, name, model_type, algorithm,
                               target_column, features, hyperparameters,
                               metrics, model_path, feature_importance,
                               training_time, created_at, updated_at)
            VALUES (?, ?, ?, 'regression', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (model_id, dataset_id, f"{algorithm}_regression_{target}",
              algorithm, target, json.dumps(features), json.dumps(kwargs),
              json.dumps({"train_rmse": train_rmse, "test_rmse": test_rmse,
                         "train_r2": train_r2, "test_r2": test_r2}),
              model_path, json.dumps(importance), 0, time.time(), time.time()))
        conn.commit()
        conn.close()
        
        return {
            "model_id": model_id,
            "algorithm": algorithm,
            "features": features,
            "target": target,
            "metrics": {
                "train_rmse": float(train_rmse), "test_rmse": float(test_rmse),
                "train_r2": float(train_r2), "test_r2": float(test_r2)
            },
            "feature_importance": importance,
            "model_path": model_path
        }

    def train_classification(self, dataset_id: str, target: str, features: List[str],
                              algorithm: str = "logistic", test_size: float = 0.2,
                              random_state: int = 42, **kwargs) -> Dict:
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required. pip install scikit-learn")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        # Encode target if categorical
        y = df[target]
        le = LabelEncoder()
        y_encoded = le.fit_transform(y.dropna())
        X = df.loc[y.dropna().index, features].dropna()
        y_encoded = y_encoded[X.index[:len(y_encoded)]]  # Align
        
        if len(X) < 10:
            return {"error": "Insufficient data"}
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=test_size, random_state=random_state, stratify=y_encoded
        )
        
        # Scale
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train model
        if algorithm == "logistic":
            model = LogisticRegression(random_state=random_state, max_iter=1000, **kwargs)
        elif algorithm == "random_forest":
            model = RandomForestClassifier(n_estimators=100, random_state=random_state, **kwargs)
        else:
            return {"error": f"Unknown algorithm: {algorithm}"}
        
        model.fit(X_train_scaled, y_train)
        
        # Predict
        y_pred_train = model.predict(X_train_scaled)
        y_pred_test = model.predict(X_test_scaled)
        y_prob_test = model.predict_proba(X_test_scaled) if hasattr(model, 'predict_proba') else None
        
        # Metrics
        train_acc = accuracy_score(y_train, y_pred_train)
        test_acc = accuracy_score(y_test, y_pred_test)
        
        # Feature importance
        if hasattr(model, 'feature_importances_'):
            importance = dict(zip(features, model.feature_importances_))
        elif hasattr(model, 'coef_'):
            importance = dict(zip(features, model.coef_[0] if model.coef_.ndim > 1 else model.coef_))
        else:
            importance = {}
        
        # Save model
        model_id = f"model_{int(time.time() * 1000) % 100000000:08d}"
        model_path = os.path.join(self.model_dir, f"{model_id}.pkl")
        
        model_data = {
            "model": model, "scaler": scaler, "label_encoder": le,
            "features": features, "target": target, "algorithm": algorithm
        }
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        # Register
        conn = get_ds_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO models (id, dataset_id, name, model_type, algorithm,
                               target_column, features, hyperparameters,
                               metrics, model_path, feature_importance,
                               training_time, created_at, updated_at)
            VALUES (?, ?, ?, 'classification', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (model_id, dataset_id, f"{algorithm}_classification_{target}",
              algorithm, target, json.dumps(features), json.dumps(kwargs),
              json.dumps({"train_accuracy": train_acc, "test_accuracy": test_acc}),
              model_path, json.dumps(importance), 0, time.time(), time.time()))
        conn.commit()
        conn.close()
        
        return {
            "model_id": model_id,
            "algorithm": algorithm,
            "features": features,
            "target": target,
            "classes": le.classes_.tolist(),
            "metrics": {
                "train_accuracy": float(train_acc), "test_accuracy": float(test_acc)
            },
            "feature_importance": importance,
            "model_path": model_path
        }

    def train_clustering(self, dataset_id: str, features: List[str],
                         algorithm: str = "kmeans", n_clusters: int = 3,
                         random_state: int = 42, **kwargs) -> Dict:
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required. pip install scikit-learn")
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. pip install pandas")
        
        dm = DatasetManager()
        df = dm.load_dataframe(dataset_id)
        if df is None:
            return {"error": "Dataset not found"}
        
        X = df[features].dropna()
        if len(X) < n_clusters:
            return {"error": "Insufficient data for clustering"}
        
        # Scale
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Train
        if algorithm == "kmeans":
            model = KMeans(n_clusters=n_clusters, random_state=random_state, **kwargs)
        else:
            return {"error": f"Unknown algorithm: {algorithm}"}
        
        labels = model.fit_predict(X_scaled)
        
        # Metrics
        inertia = model.inertia_
        
        # Add cluster labels to dataframe
        df_clustered = X.copy()
        df_clustered['cluster'] = labels
        cluster_stats = df_clustered.groupby('cluster').agg(['mean', 'std', 'count']).to_dict()
        
        # Save model
        model_id = f"model_{int(time.time() * 1000) % 100000000:08d}"
        model_path = os.path.join(self.model_dir, f"{model_id}.pkl")
        
        model_data = {
            "model": model, "scaler": scaler, "features": features,
            "algorithm": algorithm, "n_clusters": n_clusters
        }
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        # Register
        conn = get_ds_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO models (id, dataset_id, name, model_type, algorithm,
                               target_column, features, hyperparameters,
                               metrics, model_path, created_at, updated_at)
            VALUES (?, ?, ?, 'clustering', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (model_id, dataset_id, f"kmeans_clustering_{n_clusters}",
              algorithm, "", json.dumps(features), json.dumps({"n_clusters": n_clusters, **kwargs}),
              json.dumps({"inertia": float(inertia)}), model_path, time.time(), time.time()))
        conn.commit()
        conn.close()
        
        return {
            "model_id": model_id,
            "algorithm": algorithm,
            "n_clusters": n_clusters,
            "features": features,
            "inertia": float(inertia),
            "cluster_distribution": Counter(labels),
            "cluster_stats": cluster_stats,
            "model_path": model_path
        }

    def predict(self, model_id: str, input_data: Dict) -> Dict:
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required. pip install scikit-learn")
        
        model_path = os.path.join(self.model_dir, f"{model_id}.pkl")
        if not os.path.exists(model_path):
            return {"error": "Model not found"}
        
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        
        model = model_data["model"]
        scaler = model_data["scaler"]
        features = model_data["features"]
        algorithm = model_data["algorithm"]
        
        # Prepare input
        X = np.array([[input_data.get(f, 0) for f in features]])
        X_scaled = scaler.transform(X)
        
        prediction = model.predict(X_scaled)[0]
        
        result = {"prediction": float(prediction)}
        
        if "label_encoder" in model_data:
            result["prediction_label"] = model_data["label_encoder"].inverse_transform([int(prediction)])[0]
            probs = model.predict_proba(X_scaled)[0]
            result["probabilities"] = dict(zip(model_data["label_encoder"].classes_, probs))
            result["confidence"] = float(max(probs))
        
        # Save prediction
        pred_id = f"pred_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_ds_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO predictions (id, model_id, input_data, prediction,
                                    probability, input_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pred_id, model_id, json.dumps(input_data), float(prediction),
              result.get("confidence", 0), hashlib.md5(json.dumps(input_data).encode()).hexdigest(),
              time.time()))
        conn.commit()
        conn.close()
        
        return result


class WorkflowEngine:
    def __init__(self):
        pass

    def create_workflow(self, name: str, steps: List[Dict],
                        dataset_ids: List[str] = None,
                        schedule: str = None) -> str:
        workflow_id = f"wf_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_ds_connection()
        cursor = conn.cursor()
        
        next_run = None
        if schedule:
            # Simple next run calculation (would use croniter in production)
            next_run = time.time() + 86400  # Next day
        
        cursor.execute("""
            INSERT INTO workflows (id, name, description, steps,
                                  dataset_ids, schedule, next_run,
                                  created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (workflow_id, name, steps[0].get("description", "") if steps else "",
              json.dumps(steps), json.dumps(dataset_ids or []),
              schedule, next_run, time.time(), time.time()))
        conn.commit()
        conn.close()
        return workflow_id

    def run_workflow(self, workflow_id: str) -> Dict:
        conn = get_ds_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"error": "Workflow not found"}
        
        steps = json.loads(row[3]) if row[3] else []
        dataset_ids = json.loads(row[4]) if row[4] else []
        
        results = {"workflow_id": workflow_id, "steps": []}
        
        for i, step in enumerate(steps):
            step_type = step.get("type")
            step_result = {"step": i+1, "type": step_type}
            
            try:
                if step_type == "load_dataset":
                    # Already loaded
                    step_result["status"] = "completed"
                elif step_type == "eda":
                    dm = DatasetManager()
                    eda_result = EDAEngine.run_eda(step.get("dataset_id"))
                    step_result["result"] = eda_result
                    step_result["status"] = "completed"
                elif step_type == "train_model":
                    ml = MLEngine()
                    if step.get("model_type") == "regression":
                        model_result = ml.train_regression(
                            step["dataset_id"], step["target"], step["features"],
                            step.get("algorithm", "linear")
                        )
                    elif step.get("model_type") == "classification":
                        model_result = ml.train_classification(
                            step["dataset_id"], step["target"], step["features"],
                            step.get("algorithm", "logistic")
                        )
                    elif step.get("model_type") == "clustering":
                        model_result = ml.train_clustering(
                            step["dataset_id"], step["features"],
                            step.get("algorithm", "kmeans"),
                            step.get("n_clusters", 3)
                        )
                    step_result["result"] = model_result
                    step_result["status"] = "completed"
                elif step_type == "visualize":
                    viz = VisualizationEngine()
                    # Would call appropriate viz method
                    step_result["status"] = "completed"
                else:
                    step_result["status"] = "unknown_step_type"
                    
            except Exception as e:
                step_result["status"] = "error"
                step_result["error"] = str(e)
            
            results["steps"].append(step_result)
        
        # Update workflow
        conn = get_ds_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE workflows SET last_run = ?, status = 'completed',
                                updated_at = ? WHERE id = ?
        """, (time.time(), time.time(), workflow_id))
        conn.commit()
        conn.close()
        
        return results


# Module-level helpers
dm = DatasetManager()
eda_engine = EDAEngine()
stat_engine = StatisticalTestEngine()
viz_engine = VisualizationEngine()
ml_engine = MLEngine()
wf_engine = WorkflowEngine()


def ds_debug() -> str:
    conn = get_ds_connection()
    cursor = conn.cursor()
    tables = ["datasets", "data_snapshots", "analyses", "models",
              "predictions", "visualizations", "workflows", "statistical_tests"]
    output = "Data Science Agent Debug:\n"
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        output += f"  {t}: {count} records\n"
    conn.close()
    
    # Check libraries
    output += f"\nLibraries:\n"
    output += f"  pandas: {PANDAS_AVAILABLE}\n"
    output += f"  matplotlib: {MATPLOTLIB_AVAILABLE}\n"
    output += f"  scikit-learn: {SKLEARN_AVAILABLE}\n"
    output += f"  scipy: {SCIPY_AVAILABLE}\n"
    return output


def list_datasets() -> List[Dict]:
    return dm.list_datasets()


def load_dataset_csv(file_path: str, name: str = None, description: str = "") -> str:
    return dm.load_csv(file_path, name, description)


def load_dataset_json(file_path: str, name: str = None, description: str = "") -> str:
    return dm.load_json(file_path, name, description)


def create_dataset_from_dict(data: Dict, name: str, description: str = "") -> str:
    return dm.create_from_dict(data, name, description)


def get_dataset(dataset_id: str) -> Optional[Dict]:
    return dm.get_dataset(dataset_id)


def run_eda(dataset_id: str, name: str = "EDA") -> Dict:
    return eda_engine.run_eda(dataset_id, name)


def correlation_analysis(dataset_id: str, method: str = "pearson", target: str = None) -> Dict:
    return eda_engine.correlation_analysis(dataset_id, method, target)


def t_test_1sample(dataset_id: str, column: str, popmean: float) -> Dict:
    return stat_engine.t_test_1sample(dataset_id, column, popmean)


def t_test_2sample(dataset_id: str, column: str, group_column: str,
                   group1: Any, group2: Any, equal_var: bool = False) -> Dict:
    return stat_engine.t_test_2sample(dataset_id, column, group_column, group1, group2, equal_var)


def chi2_test(dataset_id: str, col1: str, col2: str) -> Dict:
    return stat_engine.chi2_test(dataset_id, col1, col2)


def anova_test(dataset_id: str, value_column: str, group_column: str) -> Dict:
    return stat_engine.anova_test(dataset_id, value_column, group_column)


def mannwhitney_test(dataset_id: str, column: str, group_column: str,
                     group1: Any, group2: Any) -> Dict:
    return stat_engine.mannwhitney_test(dataset_id, column, group_column, group1, group2)


def normality_test(dataset_id: str, column: str) -> Dict:
    return stat_engine.normality_test(dataset_id, column)


def create_histogram(dataset_id: str, column: str, bins: int = 30, kde: bool = False) -> Dict:
    return viz_engine.histogram(dataset_id, column, bins, kde)


def create_scatter(dataset_id: str, x_col: str, y_col: str,
                   color_col: str = None, size_col: str = None) -> Dict:
    return viz_engine.scatter(dataset_id, x_col, y_col, color_col, size_col)


def create_boxplot(dataset_id: str, column: str, group_column: str = None) -> Dict:
    return viz_engine.box_plot(dataset_id, column, group_column)


def create_correlation_heatmap(dataset_id: str, method: str = "pearson") -> Dict:
    return viz_engine.correlation_heatmap(dataset_id, method)


def create_pairplot(dataset_id: str, columns: List[str] = None, hue: str = None) -> Dict:
    return viz_engine.pair_plot(dataset_id, columns, hue)


def create_lineplot(dataset_id: str, x_col: str, y_cols: Union[str, List[str]]) -> Dict:
    return viz_engine.line_plot(dataset_id, x_col, y_cols)


def create_barplot(dataset_id: str, x_col: str, y_col: str, aggfunc: str = 'mean') -> Dict:
    return viz_engine.bar_plot(dataset_id, x_col, y_col, aggfunc)


def train_regression(dataset_id: str, target: str, features: List[str],
                     algorithm: str = "linear", test_size: float = 0.2) -> Dict:
    return ml_engine.train_regression(dataset_id, target, features, algorithm, test_size)


def train_classification(dataset_id: str, target: str, features: List[str],
                          algorithm: str = "logistic", test_size: float = 0.2) -> Dict:
    return ml_engine.train_classification(dataset_id, target, features, algorithm, test_size)


def train_clustering(dataset_id: str, features: List[str],
                     algorithm: str = "kmeans", n_clusters: int = 3) -> Dict:
    return ml_engine.train_clustering(dataset_id, features, algorithm, n_clusters)


def predict(model_id: str, input_data: Dict) -> Dict:
    return ml_engine.predict(model_id, input_data)


def create_workflow(name: str, steps: List[Dict],
                    dataset_ids: List[str] = None, schedule: str = None) -> str:
    return wf_engine.create_workflow(name, steps, dataset_ids, schedule)


def run_workflow(workflow_id: str) -> Dict:
    return wf_engine.run_workflow(workflow_id)