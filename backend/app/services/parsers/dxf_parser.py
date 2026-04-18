import ezdxf
from pathlib import Path
from typing import Iterator, Dict, Any, Optional, List, Set
from app.services.parsers.base import BaseParser
from app.core.exceptions import FileCorruptedException


class DXFParser(BaseParser):
    """DXF格式解析器，逐实体解析"""

    TARGET_ENTITIES = {"LINE", "POLYLINE", "LWPOLYLINE", "POINT", "INSERT", "BLOCK"}

    def __init__(self, file_path: Path):
        super().__init__(file_path)
        self._elevation_values: List[float] = []
        self._centerline_points: List[List[float]] = []
        self._cross_sections: Dict[float, List[List[float]]] = {}
        self._found_entities: Set[str] = set()

    def validate(self) -> bool:
        """验证DXF文件"""
        try:
            ezdxf.readfile(str(self.file_path))
            return True
        except Exception as e:
            raise FileCorruptedException(file_type="DXF", error=str(e))

    def parse(self) -> Iterator[Dict[str, Any]]:
        """流式解析DXF实体"""
        doc = ezdxf.readfile(str(self.file_path))
        msp = doc.modelspace()

        for entity in msp:
            self._found_entities.add(entity.dxftype())

            if entity.dxftype() == "LINE":
                yield from self._parse_line(entity)
            elif entity.dxftype() in ("POLYLINE", "LWPOLYLINE"):
                yield from self._parse_polyline(entity)
            elif entity.dxftype() == "POINT":
                yield from self._parse_point(entity)

    def _parse_line(self, entity) -> Iterator[Dict[str, Any]]:
        """解析LINE实体"""
        try:
            points = entity.get_points()
            for point in points:
                x, y, z = point[0], point[1], point[2] if len(point) > 2 else 0.0
                self._elevation_values.append(z)
                self._centerline_points.append([x, y, z])
                yield {"type": "LINE", "x": x, "y": y, "z": z}
        except Exception:
            pass

    def _parse_polyline(self, entity) -> Iterator[Dict[str, Any]]:
        """解析POLYLINE/LWPOLYLINE实体"""
        try:
            points = list(entity.get_points())
            if len(points) < 2:
                return

            # 计算平均高程作为桩号
            avg_z = sum(p[2] if len(p) > 2 else 0.0 for p in points) / len(points)

            for point in points:
                x, y, z = point[0], point[1], point[2] if len(point) > 2 else 0.0
                self._elevation_values.append(z)
                yield {"type": entity.dxftype(), "x": x, "y": y, "z": z}

            # 存储为横断面
            self._cross_sections[avg_z] = points
        except Exception:
            pass

    def _parse_point(self, entity) -> Iterator[Dict[str, Any]]:
        """解析POINT实体"""
        try:
            point = entity.dxf.location
            x, y, z = point.x, point.y, point.z if hasattr(point, 'z') else 0.0
            self._elevation_values.append(z)
            yield {"type": "POINT", "x": x, "y": y, "z": z}
        except Exception:
            pass

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
        """提取横断面"""
        cross_sections = []
        for station, points in self._cross_sections.items():
            if len(points) >= 2:
                cross_sections.append({
                    "station": station,
                    "shape": [[p[0], p[1], p[2] if len(p) > 2 else 0.0] for p in points],
                    "point_count": len(points)
                })
        return cross_sections

    def extract_elevation_range(self) -> list:
        """提取高程范围"""
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
            dist = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2) ** 0.5
            dz = abs(p2[2] - p1[2])
            if dist > 0:
                slopes.append(dz / dist)

        if not slopes:
            return {"max_slope": 0, "mean_slope": 0, "slope_distribution": {}}

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