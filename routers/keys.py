"""API Key 管理路由"""
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from db import get_db, ApiKey, UsageLog
from models import KeyCreate, KeyInfo
from sqlalchemy import func

TZ_LOCAL = timezone(timedelta(hours=8))

router = APIRouter(prefix="/admin/keys", tags=["Keys"])


@router.post("", response_model=KeyInfo)
def create_key(body: KeyCreate):
    """產生一個新的 virtual key"""
    new_key = "sk-" + secrets.token_urlsafe(32)
    db = get_db()
    try:
        obj = ApiKey(
            key=new_key, name=body.name, description=body.description,
            created_at=datetime.now(TZ_LOCAL).isoformat(), is_active=1,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("")
def list_keys():
    """列出所有 virtual keys 及用量"""
    db = get_db()
    try:
        rows = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
        return [KeyInfo.model_validate(r) for r in rows]
    finally:
        db.close()


@router.get("/usage")
def all_usage(
    start: Optional[str] = Query(None, description="開始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD"),
):
    """查詢所有 key 在指定日期範圍內的用量明細"""
    db = get_db()
    try:
        q = (
            db.query(
                UsageLog.date, UsageLog.model,
                func.sum(UsageLog.input_tokens).label("input_tokens"),
                func.sum(UsageLog.output_tokens).label("output_tokens"),
                func.sum(UsageLog.total_tokens).label("total_tokens"),
                func.sum(UsageLog.cost_usd).label("cost_usd"),
                func.count().label("requests"),
                ApiKey.id.label("key_id"),
                ApiKey.name.label("key_name"),
            )
            .join(ApiKey, UsageLog.api_key == ApiKey.key)
        )
        if start:
            q = q.filter(UsageLog.date >= start)
        if end:
            q = q.filter(UsageLog.date <= end)
        rows = (
            q.group_by(UsageLog.date, UsageLog.model, ApiKey.id, ApiKey.name)
            .order_by(UsageLog.date.desc())
            .all()
        )
        return [dict(r._mapping) for r in rows]
    finally:
        db.close()


@router.get("/{key_id}/usage")
def key_usage(key_id: int):
    """查詢某個 key 的每日用量明細"""
    db = get_db()
    try:
        key_row = db.query(ApiKey.key).filter(ApiKey.id == key_id).first()
        if not key_row:
            raise HTTPException(status_code=404, detail="Key not found")
        rows = (
            db.query(
                UsageLog.date, UsageLog.model,
                func.sum(UsageLog.input_tokens).label("input_tokens"),
                func.sum(UsageLog.output_tokens).label("output_tokens"),
                func.sum(UsageLog.total_tokens).label("total_tokens"),
                func.sum(UsageLog.cost_usd).label("cost_usd"),
                func.count().label("requests"),
            )
            .filter(UsageLog.api_key == key_row.key)
            .group_by(UsageLog.date, UsageLog.model)
            .order_by(UsageLog.date.desc())
            .all()
        )
        return [dict(r._mapping) for r in rows]
    finally:
        db.close()


@router.delete("/{key_id}")
def revoke_key(key_id: int):
    """停用一個 virtual key"""
    db = get_db()
    try:
        db.query(ApiKey).filter(ApiKey.id == key_id).update(
            {"is_active": 0}, synchronize_session=False
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {"message": "Key revoked"}


@router.post("/{key_id}/activate")
def activate_key(key_id: int):
    """重新啟用一個已撤銷的 virtual key"""
    db = get_db()
    try:
        updated = db.query(ApiKey).filter(ApiKey.id == key_id).update(
            {"is_active": 1}, synchronize_session=False
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Key not found")
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {"message": "Key activated"}


@router.patch("/{key_id}")
def update_key(key_id: int, body: KeyCreate):
    """更新 API Key 的 name 和 description"""
    db = get_db()
    try:
        key_obj = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if not key_obj:
            raise HTTPException(status_code=404, detail="Key not found")
        if body.name.strip():
            key_obj.name = body.name.strip()
        if body.description is not None:
            key_obj.description = body.description.strip()
        db.commit()
        db.refresh(key_obj)
        return KeyInfo.model_validate(key_obj)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.delete("/{key_id}/permanent")
def delete_key(key_id: int):
    """永久刪除一個 virtual key 及其用量紀錄"""
    db = get_db()
    try:
        key_obj = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if not key_obj:
            raise HTTPException(status_code=404, detail="Key not found")
        db.query(UsageLog).filter(UsageLog.api_key == key_obj.key).delete(synchronize_session=False)
        db.delete(key_obj)
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {"message": "Key deleted permanently"}
