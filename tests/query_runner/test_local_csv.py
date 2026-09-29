import os
import tempfile
from unittest import TestCase

from redash.query_runner.local_csv import LocalCSV


class TestLocalCSV(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base_path = self.tmpdir.name
        os.makedirs(os.path.join(self.base_path, "sales"))
        with open(os.path.join(self.base_path, "sales", "2026.csv"), "w", encoding="utf-8") as f:
            f.write("id,name,amount\n1,りんご,100\n2,みかん,\n")
        self.runner = LocalCSV({"base_path": self.base_path})

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_run_query_reads_relative_file(self):
        data, error = self.runner.run_query("file: sales/2026.csv", None)

        self.assertIsNone(error)
        self.assertEqual([c["name"] for c in data["columns"]], ["id", "name", "amount"])
        self.assertEqual(data["columns"][0]["type"], "integer")
        self.assertEqual(data["rows"][0]["name"], "りんご")
        self.assertIsNone(data["rows"][1]["amount"])

    def test_run_query_strips_utf8_bom(self):
        with open(os.path.join(self.base_path, "bom.csv"), "w", encoding="utf-8-sig") as f:
            f.write("id,name\n1,りんご\n")

        for query in ("file: bom.csv", "file: bom.csv\nencoding: utf-8"):
            data, error = self.runner.run_query(query, None)
            self.assertIsNone(error)
            self.assertEqual(data["columns"][0]["name"], "id")

    def test_get_schema_strips_utf8_bom(self):
        with open(os.path.join(self.base_path, "bom.csv"), "w", encoding="utf-8-sig") as f:
            f.write("id,name\n1,りんご\n")

        schema = {table["name"]: table["columns"] for table in self.runner.get_schema()}
        self.assertEqual(schema["bom.csv"], ["id", "name"])

    def test_run_query_rejects_path_outside_base(self):
        data, error = self.runner.run_query("file: ../../etc/passwd", None)

        self.assertIsNone(data)
        self.assertIn("外のファイルは参照できません", error)

    def test_run_query_requires_file(self):
        data, error = self.runner.run_query("sep: ','", None)

        self.assertIsNone(data)
        self.assertIn("file", error)

    def test_run_query_reports_missing_file(self):
        data, error = self.runner.run_query("file: sales/none.csv", None)

        self.assertIsNone(data)
        self.assertIn("ファイルが見つかりません", error)

    def test_test_connection_fails_without_mount(self):
        runner = LocalCSV({"base_path": os.path.join(self.base_path, "not_mounted")})
        with self.assertRaises(Exception) as ctx:
            runner.test_connection()
        self.assertIn("マウント", str(ctx.exception))

    def test_get_schema_lists_csv_files(self):
        schema = self.runner.get_schema()

        self.assertEqual(schema, [{"name": "sales/2026.csv", "columns": ["id", "name", "amount"]}])
