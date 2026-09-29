"""遗失物品接口：受理捡拾记录、维护失物招领信息、认领核销与批量处置。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    ActionResult,
    EntryPayload,
    LostFoundBatchPayload,
    LostFoundBatchResult,
    LostFoundClaimPayload,
    PageResult,
)
from app.services.lost_found import STATUSES, LostFoundService

router = APIRouter(prefix="/api/lost-found", tags=["遗失物品"])

service = LostFoundService()

LIST_FIELDS = [
    "物品编号",
    "物品名称",
    "物品类别",
    "物品特征",
    "捡拾地点",
    "捡拾日期",
    "捡拾人",
    "保管人",
    "认领人",
    "证件号",
    "接收人",
    "移交地点",
    "报废原因",
    "状态",
]
STATUS_LABELS = "、".join(STATUSES)


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按物品编号、名称、类别或捡拾地点检索"),
    status: str | None = Query(default=None, description=f"状态过滤：{STATUS_LABELS}"),
    pending: bool = Query(default=False, description="是否仅看待认领清单"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按关键字与状态过滤遗失物品；pending=true 时只返回待认领清单。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if status and status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"状态只支持：{STATUS_LABELS}")
    items, total = service.list_entries(
        keyword=keyword, status=status, pending_only=pending, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/pending", response_model=PageResult[dict])
def list_pending(page: int = 1, size: int = 20) -> PageResult[dict]:
    """待认领清单与单条详情共享同一份内存记录，核销或处置后立即从此清单退出。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.pending_entries(page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出现有遗失物品清单。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "lost_found", "total": total, "items": items}


@router.post("/transfer", response_model=LostFoundBatchResult)
def batch_transfer(payload: LostFoundBatchPayload) -> LostFoundBatchResult:
    """批量移交选中的待认领物品，逐条返回校验和处理结果。"""
    return _batch_dispatch("批量移交", payload)


@router.post("/scrap", response_model=LostFoundBatchResult)
def batch_scrap(payload: LostFoundBatchPayload) -> LostFoundBatchResult:
    """批量报废选中的待认领物品，逐条返回校验和处理结果。"""
    return _batch_dispatch("批量报废", payload)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条遗失物品明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"遗失物品 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """受理一条捡拾记录，物品类别、捡拾地点、保管人为必填。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="捡拾记录已受理，物品进入待认领清单", entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """维护待认领物品的失物招领信息；已核销、移交或报废的记录不再允许编辑。"""
    entry, message = service.update_entry(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/claim", response_model=ActionResult)
def claim_entry(entry_id: int, payload: LostFoundClaimPayload) -> ActionResult:
    """登记认领人与证件号，认领核销后物品退出待认领清单。"""
    entry, message = service.claim_entry(
        entry_id,
        payload.认领人,
        payload.证件号,
        payload.备注,
    )
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


def _batch_dispatch(action: str, payload: LostFoundBatchPayload) -> LostFoundBatchResult:
    values = {
        "接收人": payload.接收人,
        "移交地点": payload.移交地点,
        "报废原因": payload.报废原因,
        "备注": payload.备注,
    }
    results, message = service.run_batch_action(action, payload.ids, values)
    if message:
        raise HTTPException(status_code=400, detail=message)
    success_count = sum(1 for item in results if item["ok"])
    failure_count = len(results) - success_count
    return LostFoundBatchResult(
        ok=failure_count == 0,
        action=action,
        results=results,
        success_count=success_count,
        failure_count=failure_count,
    )
