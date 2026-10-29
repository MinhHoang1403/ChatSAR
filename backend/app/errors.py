"""Lỗi công khai ổn định; không đưa dữ liệu đầu vào hoặc secrets vào thông báo."""


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
