#!/usr/bin/env python3
"""运营族提成比例基数的配置读取与只读验证辅助函数。

默认从 Commission_Tier.Base_Rate 读取当前岗位的 Active 梯度配置；可通过
--base-rate 的调用方传入仅用于验证预期值的覆盖值。该覆盖绝不写入 Base。
配置缺失或同岗位 Active 梯度存在多个不同基数时显式失败，供调用方记录错误日志。
"""
from __future__ import annotations

from typing import Any


def link_id(value: Any) -> str | None:
    return value[0]["id"] if isinstance(value, list) and value else None


def resolve_base_rate(
    tiers: list[dict[str, Any]],
    position_record_id: str | None,
    override: float | None = None,
) -> float:
    """返回指定岗位 Active Commission_Tier 的唯一 Base_Rate，或只读覆盖值。"""
    if override is not None:
        value = float(override)
        if value < 0:
            raise ValueError(f"--base-rate 必须为非负数：{override}")
        return value
    if not position_record_id:
        raise ValueError("无法读取岗位关联，不能解析 Commission_Tier.Base_Rate")

    rates = {
        float(tier["Base_Rate"])
        for tier in tiers
        if tier.get("Status") == "Active"
        and link_id(tier.get("Position_ID")) == position_record_id
        and tier.get("Coefficient") not in (None, "")
        and tier.get("Base_Rate") not in (None, "")
    }
    if not rates:
        raise ValueError(f"运营族 Active Commission_Tier 缺少 Base_Rate 配置：岗位记录 {position_record_id}")
    if len(rates) != 1:
        raise ValueError(f"运营族 Active Commission_Tier 的 Base_Rate 配置不一致：岗位记录 {position_record_id}，值={sorted(rates)}")
    return rates.pop()
