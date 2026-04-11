from fastapi import HTTPException, status


class ReportException(HTTPException):
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
            "KNOWLEDGE_BASE_EMPTY": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "RETRIEVAL_FAILED": status.HTTP_200_OK,
            "TEMPLATE_NOT_FOUND": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "GENERATION_FAILED": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INVALID_REVISION": status.HTTP_400_BAD_REQUEST,
            "REPORT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        }
        return codes.get(self.code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class KnowledgeBaseEmptyException(ReportException):
    def __init__(self):
        super().__init__(
            code="KNOWLEDGE_BASE_EMPTY",
            message="知识库为空，无法生成报告",
            details={},
            suggestion="请先导入规范条文和历史案例"
        )


class RetrievalFailedException(ReportException):
    def __init__(self, reason: str):
        super().__init__(
            code="RETRIEVAL_FAILED",
            message="知识检索失败",
            details={"reason": reason},
            suggestion="将使用通用知识生成报告"
        )


class TemplateNotFoundException(ReportException):
    def __init__(self, template_name: str):
        super().__init__(
            code="TEMPLATE_NOT_FOUND",
            message=f"报告模板不存在: {template_name}",
            details={"template": template_name},
            suggestion="请联系管理员添加报告模板"
        )


class GenerationFailedException(ReportException):
    def __init__(self, chapter: str, reason: str):
        super().__init__(
            code="GENERATION_FAILED",
            message=f"章节生成失败: {chapter}",
            details={"chapter": chapter, "reason": reason},
            suggestion="请检查知识库内容或稍后重试"
        )


class InvalidRevisionException(ReportException):
    def __init__(self, reason: str):
        super().__init__(
            code="INVALID_REVISION",
            message="修订意见无效",
            details={"reason": reason},
            suggestion="请检查修订内容"
        )