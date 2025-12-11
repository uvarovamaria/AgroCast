# backend/app/api/v1/fields.py

import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class SoilType(str):
    """Тип почвы. Пока используем простое строковое перечисление."""
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class FieldBase(BaseModel):
    name: str = Field(..., description="Название поля/участка")
    lat: float = Field(..., ge=-90, le=90, description="Широта центра поля")
    lon: float = Field(..., ge=-180, le=180, description="Долгота центра поля")
    area_ha: Optional[float] = Field(None, description="Площадь, га (опционально)")
    has_irrigation: bool = Field(
        False,
        description="Есть ли на поле орошение (для будущих рекомендаций)",
    )
    soil_type: str = Field(
        SoilType.MEDIUM,
        description="Тип почвы: light / medium / heavy",
    )


class Field(FieldBase):
    id: str = Field(..., description="Идентификатор поля")


# Простое хранилище в памяти — достаточно для прототипа
_FAKE_DB: Dict[str, Field] = {}


@router.get("", response_model=List[Field])
async def list_fields() -> List[Field]:
    """Получить список всех сохранённых полей."""
    return list(_FAKE_DB.values())


@router.post("", response_model=Field)
async def create_field(field: FieldBase) -> Field:
    """Создать новое поле."""
    field_id = str(uuid.uuid4())
    stored = Field(id=field_id, **field.model_dump())
    _FAKE_DB[field_id] = stored
    return stored


@router.get("/{field_id}", response_model=Field)
async def get_field(field_id: str) -> Field:
    """Получить одно поле по ID."""
    field = _FAKE_DB.get(field_id)
    if field is None:
        raise HTTPException(status_code=404, detail="Поле не найдено")
    return field


@router.delete("/{field_id}")
async def delete_field(field_id: str) -> dict:
    """Удалить поле."""
    if field_id not in _FAKE_DB:
        raise HTTPException(status_code=404, detail="Поле не найдено")
    _FAKE_DB.pop(field_id)
    return {"status": "deleted", "id": field_id}
