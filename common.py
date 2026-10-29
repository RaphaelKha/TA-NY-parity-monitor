"""Shared helpers: config, logging, yfinance download with retries, idempotent parquet merge."""
import logging
import os
import sys
import time
import warnings
from pathlib import Path

import pandas as pd
import yaml

import yfinance as yf

# yfinance 1.x triggers pandas 3 deprecation warnings ("inplace keyword") on every call: pure noise.
warnings.filterwarnings("ignore", message=".*inplace keyword.*")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CONFIG_FILE = ROOT / "config.yaml"

RETRIES = 4
BACKOFF_S = 5  # 5, 10, 20 s between attempts


def setup_logging():
    logging.Formatter.converter = time.gmtime  # log timestamps in UTC like the data
    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format=f"%(asctime)s %(levelname)-7s [{Path(sys.argv[0]).stem}] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # we log failures ourselves
    return logging.getLogger("parity")


def load_config():
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def fetch(ticker, retries=RETRIES, **kwargs):
    """yfinance history() with exponential backoff on transient errors. Raises after the last attempt."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            df = yf.Ticker(ticker).history(auto_adjust=False, actions=False, raise_errors=True, **kwargs)
            if not df.empty:
                return df
            raise RuntimeError(f"{ticker} {kwargs}: empty response")
        except yf.exceptions.YFPricesMissingError as e:
            raise RuntimeError(f"{ticker} {kwargs}: no data ({e})") from None
        except Exception as e:  # network errors, rate limits...
            last_err = f"{type(e).__name__}: {e}"
        if attempt < retries:
            time.sleep(BACKOFF_S * 2 ** (attempt - 1))
    raise RuntimeError(f"{ticker} {kwargs}: {last_err}")


def to_utc(df):
    df.index = df.index.tz_convert("UTC")
    df.index.name = "ts_utc"
    return df


def merge_save(df, path):
    """Append idempotently: union with the existing file, newest download wins on duplicate timestamps."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        df = pd.concat([pd.read_parquet(path), df])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp)
    os.replace(tmp, path)  # atomic: a crash never leaves a half-written file
    return len(df)
