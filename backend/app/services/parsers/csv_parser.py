import csv
from pathlib import Path
from typing import Iterator, Dict, Any, Optional, List
from app.services.parsers.base import BaseParser
from app.core.exceptions import NoFeatureExtractedException


class CSVParser(BaseParser):
    """CSV格式流式解析器"""

    EXPECTED_COLUMNS = {"x", "y", "z", "station"}  # 最小必需列
    OPTIONAL_COLUMNS = {"point_type", "feature_id", "name"}

    def __init__(self, file_path: Path):
        super().__init__(file_path)
        self._headers: Optional[List[str]] = None
        self._elevation_values: List[float] = []
        self._centerline_points: List[List[float]] = []
        self._cross_sections: Dict[float, List[List[float]]] = {}  # station -> points

    def _detect_delimiter(self) -> str:
        """检测CSV分隔符"""
        with open(self.file_path, "r", encoding="utf-8-sig") as f:
            first_line = f.readline()
            if "," in first_line:
                return ","
            elif "\t" in first_line:
                return "\t"
            elif ";" in first_line:
                return ";"
            return ","

    def _validate_headers(self, headers: List[str]) -> None:
        """验证CSV头是否包含必需列"""
        headers_lower = {h.lower().strip() for h in headers}
        missing = self.EXPECTED_COLUMNS - headers_lower
        if missing:
            raise NoFeatureExtractedException(
                file_type="CSV",
                expected_content="x, y, z columns for coordinates",
                found_entities=list(headers_lower)
            )
        self._headers = [h.strip() for h in headers]

    def parse(self) -> Iterator[Dict[str, Any]]:
        """流式解析CSV"""
        delimiter = self._detect_delimiter()
        with open(self.file_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            self._validate_headers(reader.fieldnames or [])

            for row in reader:
                try:
                    point = {
                        "x": float(row["x"]),
                        "y": float(row["y"]),
                        "z": float(row["z"]) if "z" in row else 0.0,
                        "station": float(row["station"]) if "station" in row else 0.0,
                    }
                    # 收集高程值用于统计
                    self._elevation_values.append(point["z"])
                    # 收集中心线点
                    self._centerline_points.append([point["x"], point["y"], point["z"]])
                    yield point
                except (ValueError, KeyError):
                    continue  # 跳过无效行

    def extract_centerline(self) -> Optional[Dict[str, Any]]:
        """提取中心线"""
        if not self._centerline_points:
            return None
        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": self._centerline_points
            },
            "properties": {"count": len(self._centerline_points)}
        }

    def extract_cross_sections(self) -> list:
        """按桩号分组提取横断面"""
        if not self._centerline_points:
            return []
        # 按桩号分组
        sections_by_station = {}
        for point in self._centerline_points:
            # 简化：每个独立点作为一个断面
            station = point[2]  # 用z作为station简化
            if station not in sections_by_station:
                sections_by_station[station] = []
            sections_by_station[station].append(point)

        cross_sections = []
        for station, points in sections_by_station.items():
            cross_sections.append({
                "station": station,
                "shape": points,
                "point_count": len(points)
            })
        return cross_sections

    def extract_elevation_range(self) -> list:
        """提取高程范围 [min, max, mean]"""
        if not self._elevation_values:
            return [0.0, 0.0, 0.0]
        return [
            min(self._elevation_values),
            max(self._elevation_values),
            sum(self._elevation_values) / len(self._elevation_values)
        ]

    def extract_slope_analysis(self) -> Dict[str, Any]:
        """计算坡度统计"""
        if len(self._centerline_points) < 2:
            return {"max_slope": 0, "mean_slope": 0, "slope_distribution": {}}

        slopes = []
        for i in range(1, len(self._centerline_points)):
            p1 = self._centerline_points[i - 1]
            p2 = self._centerline_points[i]
            # 水平距离
            dist = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2) ** 0.5
            # 高差
            dz = abs(p2[2] - p1[2])
            if dist > 0:
                slope = dz / dist
                slopes.append(slope)

        if not slopes:
            return {"max_slope": 0, "mean_slope": 0, "slope_distribution": {}}

        # 坡度分级统计
        distribution = {
            "flat": len([s for s in slopes if s < 0.01]),
            "gentle": len([s for s in slopes if 0.01 <= s < 0.05]),
            "moderate": len([s for s in slopes if 0.05 <= s < 0.1]),
            "steep": len([s for s in slopes if s >= 0.1])
        }

        return {
            "max_slope": max(slopes),
            "mean_slope": sum(slopes) / len(slopes),
            "slope_distribution": distribution
        }