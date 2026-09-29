"""遗失物品业务规则：捡拾受理、旅客认领、移交与报废状态流转。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "lost_found"
REQUIRED_FIELDS = ["物品类别", "捡拾地点", "保管人"]
EDITABLE_FIELDS = REQUIRED_FIELDS + ["物品名称", "物品特征", "捡拾日期", "捡拾人", "备注"]

STATUS_PENDING = "待认领"
STATUS_CLAIMED = "已认领"
STATUS_TRANSFERRED = "已移交"
STATUS_SCRAPPED = "已报废"
STATUSES = [STATUS_PENDING, STATUS_CLAIMED, STATUS_TRANSFERRED, STATUS_SCRAPPED]
BATCH_ACTIONS = {"批量移交": STATUS_TRANSFERRED, "批量报废": STATUS_SCRAPPED}


def _clean(values: dict[str, Any], field: str) -> str:
    return str(values.get(field) or "").strip()


class LostFoundService:
    def __init__(self) -> None:
        # 种子数据只保留通用 status；补齐中文展示字段，列表和详情仍读同一行。
        for row in store.rows(MODULE):
            row.setdefault("状态", str(row.get("status") or STATUS_PENDING))

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        pending_only: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = list(store.rows(MODULE))
        if pending_only or status == STATUS_PENDING:
            rows = [row for row in rows if row.get("status") == STATUS_PENDING]
        elif status:
            rows = [row for row in rows if row.get("status") == status]
        if keyword:
            keyword = keyword.strip()
            rows = [
                row
                for row in rows
                if keyword in str(row.get("物品编号", ""))
                or keyword in str(row.get("物品名称", ""))
                or keyword in str(row.get("物品类别", ""))
                or keyword in str(row.get("捡拾地点", ""))
            ]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def pending_entries(self, page: int = 1, size: int = 20) -> tuple[list[dict[str, Any]], int]:
        return self.list_entries(status=STATUS_PENDING, page=page, size=size)

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not _clean(values, field)]
        if missing:
            return None, missing

        rows = store.rows(MODULE)
        next_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        today = date.today().isoformat()
        entry = {
            "id": next_id,
            "物品编号": f"LOST-{next_id:04d}",
            "物品名称": _clean(values, "物品名称") or _clean(values, "物品类别"),
            "物品类别": _clean(values, "物品类别"),
            "物品特征": _clean(values, "物品特征"),
            "捡拾地点": _clean(values, "捡拾地点"),
            "捡拾日期": _clean(values, "捡拾日期") or today,
            "捡拾人": _clean(values, "捡拾人"),
            "保管人": _clean(values, "保管人"),
            "认领人": "",
            "证件号": "",
            "接收人": "",
            "移交地点": "",
            "报废原因": "",
            "备注": _clean(values, "备注"),
            "状态": STATUS_PENDING,
            "status": STATUS_PENDING,
            "pending": True,
            "abnormal": False,
        }
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"遗失物品 {entry_id} 不存在或已归档"
        if entry.get("status") != STATUS_PENDING:
            return None, "只有待认领物品可以维护失物招领信息"
        missing = [field for field in REQUIRED_FIELDS if not _clean(values, field)]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        for field in EDITABLE_FIELDS:
            if field in values:
                entry[field] = _clean(values, field)
        if not entry.get("物品名称"):
            entry["物品名称"] = entry["物品类别"]
        return entry, "失物招领信息已更新"

    def claim_entry(
        self, entry_id: int, claimant: str, credential_no: str, remark: str | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"遗失物品 {entry_id} 不存在或已归档"
        if entry.get("status") != STATUS_PENDING:
            return None, f"当前状态为「{entry.get('status')}」，不能认领核销"
        claimant = claimant.strip()
        credential_no = credential_no.strip()
        if not claimant:
            return None, "认领人不能为空"
        if not credential_no:
            return None, "证件号不能为空"

        entry["认领人"] = claimant
        entry["证件号"] = credential_no
        if remark is not None:
            entry["备注"] = remark.strip()
        entry["状态"] = STATUS_CLAIMED
        entry["status"] = STATUS_CLAIMED
        entry["pending"] = False
        entry["abnormal"] = False
        return entry, "认领信息已登记，物品已核销并退出待认领清单"

    def run_batch_action(
        self, action: str, ids: list[int], values: dict[str, Any] | None = None
    ) -> tuple[list[dict[str, Any]], str]:
        values = values or {}
        if action not in BATCH_ACTIONS:
            return [], f"动作「{action}」不属于遗失物品可执行范围"

        # 选中列表可能有重复 key；去重但保留页面提交顺序，便于逐条展示结果。
        unique_ids = list(dict.fromkeys(int(entry_id) for entry_id in ids))
        if not unique_ids:
            return [], "请至少选择一条遗失物品记录"

        receiver = _clean(values, "接收人")
        transfer_place = _clean(values, "移交地点")
        scrap_reason = _clean(values, "报废原因")
        remark = _clean(values, "备注")
        if action == "批量移交" and (not receiver or not transfer_place):
            missing = []
            if not receiver:
                missing.append("接收人")
            if not transfer_place:
                missing.append("移交地点")
            return [], f"缺少必填字段：{'、'.join(missing)}"
        if action == "批量报废" and not scrap_reason:
            return [], "缺少必填字段：报废原因"

        target_status = BATCH_ACTIONS[action]
        results: list[dict[str, Any]] = []
        for entry_id in unique_ids:
            entry = self.get_entry(entry_id)
            if entry is None:
                results.append({
                    "id": entry_id,
                    "ok": False,
                    "message": f"遗失物品 {entry_id} 不存在或已归档，已跳过",
                    "entry": None,
                })
                continue
            if entry.get("status") != STATUS_PENDING:
                results.append({
                    "id": entry_id,
                    "ok": False,
                    "message": f"{entry.get('物品编号')} 当前为「{entry.get('status')}」，已跳过",
                    "entry": entry,
                })
                continue

            if target_status == STATUS_TRANSFERRED:
                entry["接收人"] = receiver
                entry["移交地点"] = transfer_place
                message = f"{entry['物品编号']} 已移交给{receiver}"
            else:
                entry["报废原因"] = scrap_reason
                message = f"{entry['物品编号']} 已按「{scrap_reason}」报废"
            if remark:
                entry["备注"] = remark
            entry["状态"] = target_status
            entry["status"] = target_status
            entry["pending"] = False
            entry["abnormal"] = False
            results.append({"id": entry_id, "ok": True, "message": message, "entry": entry})
        return results, ""
