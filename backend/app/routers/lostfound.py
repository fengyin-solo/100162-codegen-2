"""遗失物品接口：受理捡拾记录、认领核销，以及批量移交/报废的逐条校验。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    ActionResult,
    BatchActionPayload,
    BatchActionResult,
    EntryPayload,
    PageResult,
)
from app.services.lostfound import BATCH_ACTIONS, SINGLE_ACTIONS, LostFoundService

router = APIRouter(prefix="/api/lostfound", tags=["遗失物品"])

service = LostFoundService()

LIST_FIELDS = ["登记编号", "物品名称", "物品类别", "捡拾地点", "捡拾日期", "保管人", "认领人", "证件号", "状态"]
STATUSES = ["待认领", "待核销", "已移交", "已报废", "已认领"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按登记编号、物品名称或保管人检索"),
    status: str | None = Query(default=None, description="待认领、待核销、已移交、已报废、已认领"),
    waiting: bool = Query(default=False, description="只看待认领清单（待认领+待核销）"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按关键字与状态过滤遗失物品列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, status=status, waiting=waiting, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出遗失物品清单：返回当前全部数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "lostfound", "total": total, "items": items}


@router.post("/batch/actions", response_model=BatchActionResult)
def run_batch(payload: BatchActionPayload) -> BatchActionResult:
    """批量移交/报废：逐条给出校验结果，其中一条不通过只跳过该条，继续处理剩余记录。"""
    if payload.action not in BATCH_ACTIONS:
        raise HTTPException(status_code=400, detail=f"批量动作「{payload.action}」不属于遗失物品可执行范围")
    if not payload.ids:
        raise HTTPException(status_code=400, detail="请至少勾选一条记录")
    if len(payload.ids) > 200:
        raise HTTPException(status_code=400, detail="单次最多处理 200 条，请分批操作")

    # 去掉重复勾选，保留首次出现顺序，避免同一条被处理两次。
    unique_ids = list(dict.fromkeys(payload.ids))
    items = service.run_batch(payload.action, unique_ids, payload.values)
    success = sum(1 for item in items if item["ok"])
    failed = len(items) - success
    return BatchActionResult(
        ok=failed == 0,
        action=payload.action,
        total=len(items),
        success=success,
        failed=failed,
        items=items,
    )


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条遗失物品明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"遗失物品记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """受理一条捡拾记录，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="捡拾记录已受理，物品进入待认领清单", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条物品执行登记认领、认领核销、移交、报废；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    if action not in SINGLE_ACTIONS:
        return ActionResult(ok=False, message=f"动作「{action}」不属于遗失物品可执行范围")
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
