"""Diễn đạt tiếng Việt từ kết quả đã kiểm; không suy fact hoặc gọi model."""

import re
from decimal import Decimal
from typing import Any

from app.query import CompiledQuery, QueryPlan


def display_value(value: Any, kind: str) -> str:
    if value is None:
        return "chưa có giá trị"
    if kind in {"numeric", "integer"} and not isinstance(value, bool):
        # Chỉ thay dấu trên biểu diễn Decimal, không đi qua float/JS Number.
        text = format(Decimal(str(value)), "f")
        return text.replace(".", ",")
    if isinstance(value, bool):
        return "đúng" if value else "không"
    return str(value)


def column_label(column: dict[str, Any]) -> str:
    aliases = column.get("aliases") or []
    label = str(aliases[0] if aliases else column["name"]).replace("_", " ")
    # Không đưa internal ID vào prose khi tên nguồn cũng mang dạng ID kỹ thuật.
    return "giá trị đã chọn" if re.fullmatch(r"c_[a-f0-9]{32}", label) else label


def compose_answer(
    plan: QueryPlan, compiled: CompiledQuery, revision: dict[str, Any], rows: list[list[Any]]
) -> tuple[str, list[dict[str, Any]]]:
    catalog = {column["id"]: column for column in revision["columns"]}
    aggregates = {aggregate.output_id: aggregate for aggregate in plan.aggregations}
    names = {
        "SUM": "Tổng",
        "AVG": "Giá trị trung bình của",
        "MIN": "Giá trị nhỏ nhất của",
        "MAX": "Giá trị lớn nhất của",
        "COUNT_NON_NULL": "Số giá trị không trống của",
        "COUNT_DISTINCT": "Số giá trị khác nhau của",
        "COUNT_ROWS": "Số bản ghi",
    }
    output = []
    for column in compiled.columns:
        aggregate = aggregates.get(column["id"])
        if aggregate:
            label = names[aggregate.operator]
            if aggregate.column_id:
                label += " " + column_label(catalog[aggregate.column_id])
        else:
            label = column_label(catalog[column["id"]])
        output.append({**column, "label": label})
    scope = "trong dữ liệu đã chọn" + (" với điều kiện đã áp dụng" if compiled.filters else "")
    if compiled.truncated and compiled.result_mode != "top":
        return (
            f"Đang hiển thị {len(rows)} bản ghi đầu {scope}; kết quả chưa đầy đủ. "
            "Hãy thu hẹp điều kiện để xem phần còn lại.",
            output,
        )
    if not rows:
        return "Không tìm thấy bản ghi nào phù hợp với điều kiện bạn đưa ra.", output
    if plan.result_mode == "top":
        return (
            f"Dưới đây là {len(rows)} kết quả theo thứ tự đã yêu cầu "
            f"(tối đa {plan.limit}) {scope}.",
            output,
        )
    if plan.group_by:
        groups = ", ".join(column_label(catalog[key]) for key in plan.group_by)
        metrics = "; ".join(c["label"].lower() for c in output if c["id"] in aggregates)
        return f"Dưới đây là {metrics} theo từng nhóm {groups} {scope}.", output
    if plan.aggregations and not plan.select_columns and len(rows) == 1:
        sentences = []
        for column, value in zip(output, rows[0], strict=True):
            aggregate = aggregates[column["id"]]
            if value is None:
                sentences.append(
                    f"Chưa có giá trị để xác định {column['label'].lower()} {scope}; "
                    "kết quả này không được xem là 0."
                )
                continue
            number = display_value(value, column["type"])
            unit = column.get("unit")
            suffix = f" {unit}" if unit else ""
            if aggregate.operator == "COUNT_ROWS":
                sentences.append(f"Có {number} bản ghi {scope}.")
            else:
                sentences.append(f"{column['label']} {scope} là {number}{suffix}.")
        return " ".join(sentences), output
    if len(rows) == 1:
        details = []
        # Không bỏ cột trong bảng; prose giới hạn độ dài, không tự tóm tắt số liệu.
        for column, value in zip(output[:4], rows[0][:4], strict=True):
            unit = f" {column['unit']}" if column.get("unit") and value is not None else ""
            details.append(f"{column['label']}: {display_value(value, column['type'])}{unit}")
        return f"Bản ghi phù hợp {scope} có " + "; ".join(details) + ".", output
    return f"Dưới đây là {len(rows)} bản ghi phù hợp {scope}.", output


def failure_text(status: str, code: str | None = None, safe_message: str = "") -> str:
    if code == "USAGE_UNKNOWN":
        return "Một lượt mô hình trước còn thiếu usage/chi phí. Cần đối soát trước khi tiếp tục."
    if code == "DATA_PERMISSION_REQUIRED":
        return (
            "Nguồn chưa được cấp quyền gửi tới mô hình. Bạn có thể xem lại trong Quản lý dữ liệu."
        )
    if status == "clarify":
        return safe_message or "Cần làm rõ cột, điều kiện hoặc đơn vị trước khi lấy kết quả."
    if status == "unsupported":
        return "Yêu cầu vượt phạm vi hiện hỗ trợ. Hãy hỏi về một bảng đã xác nhận."
    if status == "execution_error":
        return "Chưa thể lấy kết quả từ dữ liệu. Lượt xử lý chưa có kết quả được xác minh."
    return (
        safe_message
        or "Mô hình chưa xử lý được câu hỏi. Bạn có thể xem chi tiết lỗi trước khi thử lại."
    )
