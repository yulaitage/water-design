from fastapi import HTTPException, status

class TerrainException(HTTPException):
    def __init__(self, code: str, message: str, details: dict = None, suggestion: str = None):
        self.code = code
        self.detail = {
            "code": code,
            "message": message,
            "details": details or {},
            "suggestion": suggestion
        }
        super().__init__(status_code=self._get_status_code(), detail=self.detail)

    def _get_status_code(self) -> int:
        codes = {
            "FILE_TOO_LARGE": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "INVALID_FILE_TYPE": status.HTTP_400_BAD_REQUEST,
            "FILE_CORRUPTED": status.HTTP_400_BAD_REQUEST,
            "NO_FEATURE_EXTRACTED": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PARTIAL_PARSING": status.HTTP_200_OK,  # 部分成功
        }
        return codes.get(self.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

class FileTooLargeException(TerrainException):
    def __init__(self, max_size: int, actual_size: int):
        super().__init__(
            code="FILE_TOO_LARGE",
            message=f"文件大小超过限制",
            details={"max_size": max_size, "actual_size": actual_size},
            suggestion=f"请上传小于{max_size // (1024*1024*1024)}GB的文件"
        )

class InvalidFileTypeException(TerrainException):
    def __init__(self, file_type: str, allowed_types: list):
        super().__init__(
            code="INVALID_FILE_TYPE",
            message=f"不支持的文件格式: {file_type}",
            details={"file_type": file_type, "allowed_types": allowed_types},
            suggestion="请上传CSV或DXF格式文件"
        )

class FileCorruptedException(TerrainException):
    def __init__(self, file_type: str, error: str):
        super().__init__(
            code="FILE_CORRUPTED",
            message=f"文件损坏或格式错误",
            details={"file_type": file_type, "error": error},
            suggestion="请检查文件是否完整，或尝试重新导出"
        )

class NoFeatureExtractedException(TerrainException):
    def __init__(self, file_type: str, expected_content: str, found_entities: list):
        super().__init__(
            code="NO_FEATURE_EXTRACTED",
            message=f"无法从文件中提取有效地形特征",
            details={
                "detected_format": file_type,
                "expected_content": expected_content,
                "found_entities": found_entities
            },
            suggestion="请检查文件是否包含高程坐标信息"
        )