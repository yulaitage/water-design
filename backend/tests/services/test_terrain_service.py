import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from app.services.terrain_service import TerrainService, MAX_FILE_SIZE
from app.core.exceptions import FileTooLargeException, InvalidFileTypeException


class TestTerrainService:
    def test_validate_file_size_raises_when_too_large(self):
        service = TerrainService(db=AsyncMock())
        large_content = b"x" * (11 * 1024 * 1024 * 1024)  # 11GB

        with pytest.raises(FileTooLargeException):
            service._validate_file(large_content, "test.csv")

    def test_validate_file_type_raises_for_pdf(self):
        service = TerrainService(db=AsyncMock())

        with pytest.raises(InvalidFileTypeException):
            service._validate_file(b"test content", "test.pdf")

    def test_validate_dxf_magic_number_raises(self):
        service = TerrainService(db=AsyncMock())
        # DXF without AutoCAD magic number
        content = b"INVALID_DXF_DATA"

        with pytest.raises(InvalidFileTypeException):
            service._validate_file(content, "test.dxf")

    def test_validate_csv_passes(self):
        service = TerrainService(db=AsyncMock())
        content = b"x,y,z,station\n0,0,0,0\n"

        # Should not raise
        service._validate_file(content, "test.csv")