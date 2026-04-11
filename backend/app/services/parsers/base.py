from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, Optional
from pathlib import Path


class BaseParser(ABC):
    """地形文件解析器基类"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._line_count: Optional[int] = None

    @abstractmethod
    def parse(self) -> Iterator[Dict[str, Any]]:
        """流式解析文件，返回地理特征迭代器"""
        pass

    @abstractmethod
    def extract_centerline(self) -> Optional[Dict[str, Any]]:
        """提取河道中心线"""
        pass

    @abstractmethod
    def extract_cross_sections(self) -> list:
        """提取横断面"""
        pass

    @abstractmethod
    def extract_elevation_range(self) -> list:
        """提取高程范围 [min, max, mean]"""
        pass

    @abstractmethod
    def extract_slope_analysis(self) -> Dict[str, Any]:
        """提取坡度分析"""
        pass

    def get_bounds(self) -> Optional[Dict[str, Any]]:
        """获取边界框"""
        pass

    def validate(self) -> bool:
        """验证文件格式是否正确"""
        pass