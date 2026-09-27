"""遗失物品业务规则：捡拾受理、认领核销、移交报废与逐条批量校验都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "lostfound"

REQUIRED_FIELDS = ["物品名称", "物品类别", "捡拾地点", "保管人"]
LIST_FIELDS = [
    "登记编号",
    "物品名称",
    "物品类别",
    "捡拾地点",
    "捡拾日期",
    "保管人",
    "认领人",
    "证件号",
    "状态",
]

# 待认领清单覆盖「待认领」「待核销」两种状态；认领核销、移交、报废后退出。
STATUS_PENDING = "待认领"
STATUS_CLAIMED = "待核销"
STATUS_HANDED = "已移交"
STATUS_SCRAPPED = "已报废"
STATUS_VERIFIED = "已认领"
WAITING_STATUSES = [STATUS_PENDING, STATUS_CLAIMED]
# 只有还在招领架上的物品才能批量移交/报废。
BATCHABLE_STATUSES = [STATUS_PENDING]

SINGLE_ACTIONS = ["登记认领", "认领核销", "移交", "报废"]
BATCH_ACTIONS = ["批量移交", "批量报废"]

KEYWORD_FIELDS = ["登记编号", "物品名称", "保管人", "认领人"]


def _today() -> str:
    return date.today().isoformat()


class LostFoundService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        waiting: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if waiting:
            rows = [row for row in rows if row.get("status") in WAITING_STATUSES]
        elif status:
            rows = [row for row in rows if row.get("status") == status]
        if keyword:
            rows = [
                row
                for row in rows
                if any(keyword in str(row.get(field) or "") for field in KEYWORD_FIELDS)
            ]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        # 列表与单条明细都读同一份仓库对象，状态天然一致。
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        entry: dict[str, Any] = {
            "id": entry_id,
            "登记编号": f"LOST-{entry_id:04d}",
            "物品名称": str(values.get("物品名称")).strip(),
            "物品类别": str(values.get("物品类别")).strip(),
            "捡拾地点": str(values.get("捡拾地点")).strip(),
            "捡拾日期": str(values.get("捡拾日期") or _today()).strip(),
            "保管人": str(values.get("保管人")).strip(),
            "捡拾经过": str(values.get("捡拾经过") or "").strip(),
            "认领人": "",
            "证件号": "",
            "移交去向": "",
            "移交时间": "",
            "报废原因": "",
            "报废时间": "",
        }
        entry["状态"] = STATUS_PENDING
        self._sync(entry, STATUS_PENDING)
        rows.append(entry)
        return entry, []

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"遗失物品记录 {entry_id} 不存在"
        return self._apply(entry, action, values or {})

    def run_batch(
        self, action: str, ids: list[int], values: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """逐条校验处理：某条不通过只记录失败并跳过，继续处理剩余记录。"""
        results: list[dict[str, Any]] = []
        for entry_id in ids:
            entry = store.find(MODULE, int(entry_id))
            if entry is None:
                results.append({
                    "id": int(entry_id),
                    "ok": False,
                    "message": f"记录 {entry_id} 不存在",
                    "entry": None,
                })
                continue
            updated, message = self._apply(entry, action, values or {})
            results.append({
                "id": int(entry_id),
                "ok": updated is not None,
                "message": message,
                "entry": updated,
            })
        return results

    # ---- 内部规则 -------------------------------------------------------

    def _apply(
        self, entry: dict[str, Any], action: str, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        current = entry.get("status")

        if action == "登记认领":
            if current != STATUS_PENDING:
                return None, f"当前状态「{current}」不可登记认领，仅待认领物品可登记"
            claimer = str(values.get("认领人") or "").strip()
            cert_no = str(values.get("证件号") or "").strip()
            missing: list[str] = []
            if not claimer:
                missing.append("认领人")
            if not cert_no:
                missing.append("证件号")
            if missing:
                return None, f"缺少必填信息：{'、'.join(missing)}"
            entry["认领人"] = claimer
            entry["证件号"] = cert_no
            self._sync(entry, STATUS_CLAIMED)
            return entry, "认领信息已登记，等待核销"

        if action == "认领核销":
            if current != STATUS_CLAIMED:
                return None, f"当前状态「{current}」不可核销，仅待核销记录可核销"
            self._sync(entry, STATUS_VERIFIED)
            return entry, "认领已核销，物品退出待认领清单"

        if action in ("移交", "批量移交"):
            if current not in BATCHABLE_STATUSES:
                return None, f"当前状态「{current}」不可移交，仅待认领物品可移交"
            target = str(values.get("移交去向") or "").strip()
            if not target:
                return None, "缺少必填信息：移交去向"
            entry["移交去向"] = target
            entry["移交时间"] = _today()
            self._sync(entry, STATUS_HANDED)
            return entry, f"物品已移交至{target}"

        if action in ("报废", "批量报废"):
            if current not in BATCHABLE_STATUSES:
                return None, f"当前状态「{current}」不可报废，仅待认领物品可报废"
            reason = str(values.get("报废原因") or "").strip() or "未填写"
            entry["报废原因"] = reason
            entry["报废时间"] = _today()
            self._sync(entry, STATUS_SCRAPPED)
            return entry, "物品已报废"

        return None, f"动作「{action}」不属于遗失物品可执行范围"

    def _sync(self, entry: dict[str, Any], status: str) -> None:
        """status 与中文「状态」列写同一份值，保证列表、明细口径一致。"""
        entry["status"] = status
        entry["状态"] = status
        entry["pending"] = status in WAITING_STATUSES
        entry["abnormal"] = False
