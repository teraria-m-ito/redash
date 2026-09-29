import logging
import os

import yaml

from redash.query_runner import register
from redash.query_runner.csv import CSV

logger = logging.getLogger(__name__)

try:
    import numpy as np
    import pandas as pd
except ImportError:
    np = None
    pd = None

DEFAULT_BASE_PATH = "/data/csv"
DEFAULT_ENCODING = "utf-8"
BOM_AWARE_UTF8 = "utf-8-sig"
UTF8_ALIASES = ("utf-8", "utf8", "utf_8")
CSV_EXTENSION = ".csv"
MAX_SCHEMA_FILES = 500


class LocalPathError(Exception):
    pass


def normalize_encoding(encoding):
    # utf-8-sig は BOM の有無どちらでも読めるため、UTF-8 指定はすべて置き換える
    if (encoding or "").strip().lower() in UTF8_ALIASES:
        return BOM_AWARE_UTF8
    return encoding


class LocalCSV(CSV):
    @classmethod
    def name(cls):
        return "Local CSV"

    @classmethod
    def type(cls):
        return "local_csv"

    @classmethod
    def configuration_schema(cls):
        return {
            "type": "object",
            "properties": {
                "base_path": {
                    "type": "string",
                    "title": "Base Directory (コンテナ内のパス)",
                    "default": DEFAULT_BASE_PATH,
                },
                "encoding": {
                    "type": "string",
                    "title": "Default Encoding (例: utf-8, cp932。BOM 付き utf-8 の場合は utf-8-sig を指定)",
                    "default": DEFAULT_ENCODING,
                },
            },
            "order": ["base_path", "encoding"],
            "required": ["base_path"],
        }

    @property
    def base_path(self):
        return self.configuration.get("base_path") or DEFAULT_BASE_PATH

    @property
    def default_encoding(self):
        return normalize_encoding(self.configuration.get("encoding") or DEFAULT_ENCODING)

    def test_connection(self):
        if not os.path.isdir(self.base_path):
            raise Exception(
                "ディレクトリ {} がコンテナ内に存在しません。ホスト側ディレクトリを server / worker コンテナへ"
                "マウントしているか確認してください。".format(self.base_path)
            )
        if not os.access(self.base_path, os.R_OK | os.X_OK):
            raise Exception("ディレクトリ {} を読み取る権限がありません。".format(self.base_path))

    def run_query(self, query, user):
        try:
            args = yaml.safe_load(query) or {}
        except yaml.YAMLError as e:
            return None, "YAML の解析に失敗しました: {}".format(e)

        if not isinstance(args, dict) or not args.get("file"):
            return None, "file にベースディレクトリ（{}）からの相対パスを指定してください。".format(self.base_path)

        relative_path = str(args.pop("file"))
        args.setdefault("sep", ",")
        args["encoding"] = normalize_encoding(args.get("encoding") or self.default_encoding)

        try:
            base = os.path.realpath(self.base_path)
            path = os.path.realpath(os.path.join(base, relative_path))
            if os.path.commonpath([base, path]) != base:
                raise LocalPathError(
                    "ベースディレクトリ（{}）の外のファイルは参照できません: {}".format(self.base_path, relative_path)
                )
            if not os.path.isfile(path):
                raise LocalPathError(
                    "ファイルが見つかりません: {}（コンテナ内パス）。ホスト側のファイルがマウント先に"
                    "配置されているか確認してください。".format(path)
                )

            df = pd.read_csv(path, **args)
            data = {"columns": [], "rows": []}
            conversions = [
                {"pandas_type": np.integer, "redash_type": "integer"},
                {"pandas_type": np.inexact, "redash_type": "float"},
                {
                    "pandas_type": np.datetime64,
                    "redash_type": "datetime",
                    "to_redash": lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
                },
                {"pandas_type": np.bool_, "redash_type": "boolean"},
                {"pandas_type": np.object_, "redash_type": "string"},
            ]
            labels = []
            for dtype, label in zip(df.dtypes, df.columns):
                for conversion in conversions:
                    if issubclass(dtype.type, conversion["pandas_type"]):
                        data["columns"].append(
                            {"name": label, "friendly_name": label, "type": conversion["redash_type"]}
                        )
                        labels.append(label)
                        func = conversion.get("to_redash")
                        if func:
                            df[label] = df[label].apply(func)
                        break
            data["rows"] = df[labels].replace({np.nan: None}).to_dict(orient="records")
            error = None
        except KeyboardInterrupt:
            error = "Query cancelled by user."
            data = None
        except LocalPathError as e:
            error = str(e)
            data = None
        except Exception as e:
            error = "Error reading {0}. {1}".format(relative_path, str(e))
            data = None

        return data, error

    def get_schema(self, get_stats=False):
        self.test_connection()

        base = os.path.realpath(self.base_path)
        schema = []
        for root, dirs, files in os.walk(base):
            dirs.sort()
            for filename in sorted(files):
                if not filename.lower().endswith(CSV_EXTENSION):
                    continue
                if len(schema) >= MAX_SCHEMA_FILES:
                    return schema

                full_path = os.path.join(root, filename)
                try:
                    header = pd.read_csv(full_path, nrows=0, encoding=self.default_encoding)
                    columns = [str(column) for column in header.columns]
                except Exception as e:
                    logger.warning("Failed to read header of %s: %s", full_path, e)
                    columns = []
                schema.append({"name": os.path.relpath(full_path, base), "columns": columns})
        return schema


register(LocalCSV)
