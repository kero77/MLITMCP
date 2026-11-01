"""抽出する項目のスキーマ。LLM の構造化出力（JSON Schema）にもそのまま使う。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LeaseContract(BaseModel):
    """賃貸借契約書から抽出する項目。契約書に無い項目は null にする。"""

    property_name: Optional[str] = Field(None, description="物件名")
    property_address: Optional[str] = Field(None, description="物件所在地")
    room_number: Optional[str] = Field(None, description="部屋番号・区画")
    lessor: Optional[str] = Field(None, description="貸主（賃貸人）")
    lessee: Optional[str] = Field(None, description="借主（賃借人）")
    contract_start: Optional[str] = Field(None, description="契約開始日 YYYY-MM-DD")
    contract_end: Optional[str] = Field(None, description="契約終了日 YYYY-MM-DD")
    monthly_rent: Optional[int] = Field(None, description="月額賃料（円）")
    common_fee: Optional[int] = Field(None, description="共益費・管理費（円/月）")
    deposit: Optional[int] = Field(None, description="敷金・保証金（円）")
    key_money: Optional[int] = Field(None, description="礼金（円）")
    renewal_terms: Optional[str] = Field(None, description="更新条件・更新料")
    usage: Optional[str] = Field(None, description="使用目的（居住用/事務所用など）")
    special_terms: Optional[str] = Field(None, description="特約事項の要約")


class RentRollRow(BaseModel):
    """レントロール 1 行（1 区画）。"""

    room_number: Optional[str] = Field(None, description="部屋番号")
    tenant: Optional[str] = Field(None, description="入居者名。空室なら null")
    is_vacant: Optional[bool] = Field(None, description="空室か")
    area_sqm: Optional[float] = Field(None, description="専有面積（㎡）")
    monthly_rent: Optional[int] = Field(None, description="月額賃料（円）")
    common_fee: Optional[int] = Field(None, description="共益費（円/月）")
    deposit: Optional[int] = Field(None, description="敷金（円）")
    contract_start: Optional[str] = Field(None, description="契約開始日 YYYY-MM-DD")
    contract_end: Optional[str] = Field(None, description="契約終了日 YYYY-MM-DD")


class RentRollChunk(BaseModel):
    rows: list[RentRollRow]
