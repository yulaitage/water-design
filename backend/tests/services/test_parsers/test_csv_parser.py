import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from app.services.parsers.csv_parser import CSVParser
from app.core.exceptions import NoFeatureExtractedException


class TestCSVParser:
    def test_parse_valid_csv(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("x,y,z,station\n100.0,200.0,10.5,0\n100.5,200.5,10.3,10\n")

        parser = CSVParser(csv_file)
        points = list(parser.parse())

        assert len(points) == 2
        assert points[0]["x"] == 100.0
        assert points[0]["z"] == 10.5

    def test_extract_elevation_range(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("x,y,z,station\n100.0,200.0,10.0,0\n100.5,200.5,20.0,10\n")

        parser = CSVParser(csv_file)
        list(parser.parse())
        elev_range = parser.extract_elevation_range()

        assert elev_range == [10.0, 20.0, 15.0]

    def test_extract_centerline(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("x,y,z,station\n100.0,200.0,10.5,0\n100.5,200.5,10.3,10\n")

        parser = CSVParser(csv_file)
        list(parser.parse())
        centerline = parser.extract_centerline()

        assert centerline is not None
        assert centerline["geometry"]["type"] == "LineString"
        assert len(centerline["geometry"]["coordinates"]) == 2

    def test_missing_columns_raises(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("x,y\n100.0,200.0\n")

        parser = CSVParser(csv_file)
        with pytest.raises(NoFeatureExtractedException):
            list(parser.parse())

    def test_slope_analysis(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("x,y,z,station\n0.0,0.0,0.0,0\n1.0,0.0,1.0,10\n")

        parser = CSVParser(csv_file)
        list(parser.parse())
        slope = parser.extract_slope_analysis()

        assert "max_slope" in slope
        assert "mean_slope" in slope
        assert slope["max_slope"] == 1.0  # 1m rise over 1m run