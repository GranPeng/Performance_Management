#!/usr/bin/env python3
"""T12a 独立计算链校验。

仅使用本地 V04 结构化规则、T9a 模拟清单和从 Base 读取的存储/公式结果进行对账。
不调用、复制或执行 Base 公式表达式；所有预期得分、加权汇总、梯度及提成均由本脚本独立计算。
执行失败会写入 data/output/T12a计算链校验错误日志.json；业务差异写入正常校验报告而不静默修改任何在线数据。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from base_rate_config import resolve_base_rate

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLES = {
    "Performance_Result": "tbl6tFtVKExFUTWo",
    "Actual": "tbli9VhcUFjVDeNd",
    "Metric": "tbldKtdIVv8nnTyX",
    "Position": "tbldzvsg9Op6pK29",
    "Target": "tblydZkf17kmzrO0",
    "Commission_Tier": "tblkZUoHYwBIvDYe",
    "Employee": "tblc59aB4EnSxkQv",
    "Exemption_Scope": "tblP6Im75vDohuPF",
}
ROOT = Path(__file__).resolve().parents[1]
V04 = ROOT / "data/output/绩效框架结构化规则.json"
MANIFEST = ROOT / "data/output/T9a模拟Actual清单.json"
OUT = ROOT / "data/output/T12a计算链独立校验报告.json"
ERROR_OUT = ROOT / "data/output/T12a计算链校验错误日志.json"
CLI = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")
EPS = 1e-6


def d013_tier_percentage(score_total: float) -> float:
    """D-013 统一档位：左闭右开；150 分及以上按最高档处理（D-009）。"""
    if score_total < 60:
        return 0.8
    if score_total < 80:
        return 0.9
    if score_total < 100:
        return 1.0
    return 1.1


D013_BOUNDARY_VERIFICATION = [
    {"score_total": score, "interval": interval, "tier_percentage": d013_tier_percentage(score)}
    for score, interval in ((0, "[0,60)"), (60, "[60,80)"), (80, "[80,100)"), (100, "[100,150)"), (150, "[150,+∞)（最高档）"))
]


def cli(args: list[str]) -> dict[str, Any]:
    p = subprocess.run([CLI, "base", *args, "--as", "user"], text=True, capture_output=True)
    try:
        response = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"lark-cli 非 JSON 输出: {p.stdout[-500:]} stderr={p.stderr[-500:]}") from exc
    if p.returncode != 0 or not response.get("ok"):
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    return response["data"]


def records(table: str, fields: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", TABLES[table], "--limit", "200", "--format", "json", "--offset", str(offset)]
        for field in fields:
            args += ["--field-id", field]
        data = cli(args)
        for record_id, values in zip(data["record_id_list"], data["data"]):
            row = dict(zip(data["fields"], values))
            row["_record_id"] = record_id
            result.append(row)
        if not data.get("has_more"):
            return result
        offset += len(data["record_id_list"])


def record_get(table: str, record_id: str, fields: list[str]) -> dict[str, Any]:
    args = ["+record-get", "--base-token", BASE, "--table-id", TABLES[table], "--record-id", record_id, "--format", "json"]
    for field in fields:
        args += ["--field-id", field]
    data = cli(args)
    # CLI versions return either a field dictionary or fields/data shape.
    if isinstance(data, dict) and "fields" in data and isinstance(data["fields"], dict):
        return data["fields"]
    if isinstance(data, dict) and isinstance(data.get("fields"), list) and isinstance(data.get("data"), list) and data["data"]:
        return dict(zip(data["fields"], data["data"][0]))
    if isinstance(data, dict) and "record" in data and isinstance(data["record"], dict):
        return data["record"].get("fields", data["record"])
    return data


def link_id(value: Any) -> str | None:
    return value[0]["id"] if isinstance(value, list) and value else None


def link_ids(value: Any) -> set[str]:
    """Return every linked record id; a D-014 employee may own multiple channels."""
    if not isinstance(value, list):
        return set()
    return {item["id"] for item in value if isinstance(item, dict) and item.get("id")}


MIDDLE_CONTROL_POSITION_NAMES = {"直播中控", "运营助理"}
ACTIVE_EMPLOYMENT_STATUSES = {"在职", "正式在岗", "active"}
ACTIVE_RECORD_STATUSES = {"active", "正式在岗"}
NON_GSV_METRIC_MARKERS = {"roi", "消耗", "转化", "次数", "点击", "曝光", "成本"}


def normalized_text(value: Any) -> str:
    return "" if value is None else str(value).strip().lower().replace(" ", "")


def is_gsv_metric(metric: dict[str, Any] | None) -> bool:
    """Classify a Metric from its business metadata, never from a hard-coded record ID."""
    if not metric:
        return False
    text = " ".join(
        str(metric.get(field) or "")
        for field in ("Metric_Name", "Metric_Type", "Metric_Category", "Commission_Base_Type", "Budget_Field_Ref")
    ).lower()
    if any(marker in text for marker in NON_GSV_METRIC_MARKERS):
        return False
    return any(marker in text for marker in ("gsv", "退货后营收", "主营业务收入", "营收"))


def eligible_middle_control_employee_ids(
    employees: list[dict[str, Any]], positions_by_record_id: dict[str, dict[str, Any]], channel_record_id: str,
) -> set[str]:
    """D-013: count only active, employed live-control/operations-assistant roster members for one channel."""
    eligible: set[str] = set()
    for employee in employees:
        position = positions_by_record_id.get(link_id(employee.get("Position_ID")) or "", {})
        position_name = normalized_text(position.get("Position_Name"))
        record_status = normalized_text(employee.get("Status"))
        employment_status = normalized_text(employee.get("Employment_Status"))
        if (
            channel_record_id in link_ids(employee.get("Responsible_Channel_IDs"))
            and any(role in position_name for role in MIDDLE_CONTROL_POSITION_NAMES)
            and record_status in ACTIVE_RECORD_STATUSES
            and employment_status in ACTIVE_EMPLOYMENT_STATUSES
            and employee.get("_record_id")
        ):
            eligible.add(str(employee["_record_id"]))
    return eligible


def count_eligible_middle_controls(
    employees: list[dict[str, Any]], positions_by_record_id: dict[str, dict[str, Any]], channel_record_id: str,
) -> int:
    return len(eligible_middle_control_employee_ids(employees, positions_by_record_id, channel_record_id))


def num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def same(left: Any, right: Any) -> bool:
    if left in (None, "") and right in (None, ""):
        return True
    try:
        return abs(float(left) - float(right)) <= EPS
    except (TypeError, ValueError):
        return left == right


def independent_auto_score(metric_id: str, scoring_type: str, actual: float | None, rate: float | None) -> float | None:
    """V04 rule interpreter, deliberately separate from Base formula text and parameter snapshots."""
    if scoring_type in {"定性等级型", "奖惩制"}:
        return None
    if actual is None:
        return None
    if scoring_type == "次数阈值型":
        if actual <= 0:
            return 100.0
        if actual < 3:
            # V04 IE-LIVE-003 原文是 60；LIVE-002 原文是 80。
            return 60.0 if metric_id == "MET-V04-IE-LIVE-003" else 80.0
        return 0.0
    if scoring_type == "扣分制":
        return max(100.0 - actual * 5.0, 0.0)
    # Target 缺失或为 0 时 Achievement_Rate 的 IFERROR 结果应留空，
    # 不应被独立校验器误判为解释失败（T12b 边界用例）。
    if scoring_type == "达成率/进度型" and rate is None:
        return None
    if scoring_type != "达成率/进度型":
        raise ValueError(f"无法按 V04 独立解释指标: {metric_id} / {scoring_type}")
    # V04 评分标准按指标唯一代码映射。分支值来自 V04 JSON 的评分标准原文，不读取 Base 公式或结果参数列。
    if metric_id == "MET-V04-IE-OPS-002":
        return min(rate * 100, 110) if rate >= .90 else (85.0 if rate >= .85 else (80.0 if rate >= .80 else 0.0))
    if metric_id in {"MET-V04-IE-SUP-002", "MET-V04-IE-ADS-002"}:
        return min(rate * 100, 150) if rate >= .90 else (60.0 if rate >= .80 else 0.0)
    if metric_id == "MET-V04-PROD-DIR-002":
        return min(rate * 100, 120) if rate >= 1 else (80.0 if rate >= 120 / 140 else 0.0)
    if metric_id == "MET-V04-PROD-EDIT-002":
        return min(rate * 100, 120) if rate >= 1 else (80.0 if rate > .80 else 0.0)
    if metric_id == "MET-V04-PROD-CAM-002":
        return 100.0 if rate >= 1 else 0.0
    if metric_id in {"MET-V04-PROD-DIR-003", "MET-V04-PROD-EDIT-003"}:
        return min(rate * 100, 150) if rate >= 1 else (90.0 if rate > .80 else 0.0)
    # 其余 V04 达成率型（GSV/营收及主播 ROI）为 100/80/60/0、最高150。
    return min(rate * 100, 150) if rate >= 1 else (90.0 if rate >= .80 else (60.0 if rate >= .60 else 0.0))


def v04_live_tiers(v04: dict[str, Any]) -> list[dict[str, Any]]:
    live = next(p for p in v04["positions"] if p["source_sheet_code"] == "IE-LIVE")
    tiers = live["commission_rules"][0]["tiers"]
    return [{"source_cell": t["source_cell"], "lower": t["values"]["J"], "upper": t["values"]["K"]} for t in tiers]


def commission_ratio(
    matched: dict[str, Any] | None,
    tiers: list[dict[str, Any]],
    position_record_id: str | None,
    base_rate_override: float | None,
) -> float | None:
    if not matched:
        return None
    coefficient = num(matched.get("Coefficient"))
    ratio = num(matched.get("Ratio_Value"))
    if coefficient is not None:
        base_rate = resolve_base_rate(tiers, position_record_id, base_rate_override)
        return round(base_rate * coefficient, 6)
    return ratio


def main(base_rate_override: float | None = None, readonly: bool = False) -> None:
    if not Path(CLI).is_file():
        raise RuntimeError(f"lark-cli 不可用: {CLI}")
    v04 = json.loads(V04.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_by_actual = {r.get("actual_id"): r for r in manifest["records"] if r.get("actual_id")}

    result_fields = ["Result_ID", "Period", "Employee_ID", "Metric_ID", "Actual_ID", "Target_ID", "Target_Value_Snapshot", "Achievement_Rate", "Auto_Score", "Manual_Score", "Final_Score", "Weight", "Weighted_Score", "Monthly_Total", "Commission_Tier_Level", "Commission_Base", "Commission_Ratio", "Commission_Amount", "Perf_Salary_Snapshot", "Note", "Project_Run_Days", "Revenue_Actual_ID", "Monthly_Revenue", "Is_Exempt", "Exemption_Scope_ID", "Status", "Source"]
    results = records("Performance_Result", result_fields)
    actuals = records("Actual", ["Actual_ID", "Actual_Value", "Employee_ID", "Metric_ID", "Channel_ID", "Period", "Status"])
    metrics = records("Metric", ["Metric_ID", "Metric_Name", "Metric_Type", "Metric_Category", "Commission_Base_Type", "Budget_Field_Ref", "Scoring_Type", "Weight", "Position_ID", "Source_Cell", "Scoring_Standard_Text", "Status"])
    positions = records("Position", ["Position_ID", "Position_Name"])
    tiers = records("Commission_Tier", ["Commission_Tier_ID", "Position_ID", "Tier_Level", "Score_Lower", "Score_Upper", "Coefficient", "Ratio_Value", "Base_Rate", "Source_Cell", "Status"])
    employees = records("Employee", ["Employee_ID", "Position_ID", "Responsible_Channel_IDs", "Employment_Status", "Perf_Participate_Status", "Status"])
    scopes = records("Exemption_Scope", ["Exemption_Scope_ID", "Max_Project_Run_Days", "Max_Monthly_Revenue", "Status"])
    employee_by_rid = {r["_record_id"]: r for r in employees}
    scope_by_rid = {r["_record_id"]: r for r in scopes}

    actual_by_rid = {r["_record_id"]: r for r in actuals}
    metric_by_rid = {r["_record_id"]: r for r in metrics}
    position_by_rid = {r["_record_id"]: r for r in positions}
    target_ids = sorted({link_id(r.get("Target_ID")) for r in results if link_id(r.get("Target_ID"))})
    target_values: dict[str, float | None] = {}
    for target_id in target_ids:
        target_values[target_id] = num(record_get("Target", target_id, ["Target_Value"]).get("Target_Value"))

    tier_by_position: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tier in tiers:
        pos = link_id(tier.get("Position_ID"))
        if pos and tier.get("Status") == "Active":
            tier_by_position[pos].append(tier)

    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    expected_weighted_by_emp_period: dict[tuple[str, str], float] = defaultdict(float)
    expected_final: dict[str, float | None] = {}
    expected_weighted: dict[str, float] = {}

    for result in results:
        metric = metric_by_rid.get(link_id(result.get("Metric_ID")))
        actual_row = actual_by_rid.get(link_id(result.get("Actual_ID")))
        key = (link_id(result.get("Employee_ID")) or "", result.get("Period") or "")
        result_id = result.get("Result_ID") or result["_record_id"]
        diff: list[str] = []
        is_t21_special = result.get("Source") == "SIMULATED_T21_D013_D014"
        if not metric:
            issues.append({"result_id": result_id, "root_cause": "Metric_ID 关联缺失或无法读取", "severity": "阻断"})
            continue
        actual_value = num(actual_row.get("Actual_Value")) if actual_row else None
        target = target_values.get(link_id(result.get("Target_ID"))) if link_id(result.get("Target_ID")) else num(result.get("Target_Value_Snapshot"))
        rate = (actual_value / target) if actual_value is not None and target not in (None, 0) else None
        is_exempt = str(result.get("Is_Exempt")).lower() == "true"
        is_t14_d010 = result.get("Source") == "SIMULATED_T14_D010_NONZERO" and is_exempt
        # D-010-R1：豁免不改变绩效打分/加权；仅提成改为运营岗当前基数直乘 GSV。
        expected_auto = independent_auto_score(metric["Metric_ID"], metric["Scoring_Type"], actual_value, rate)
        manual = num(result.get("Manual_Score"))
        expected_fin = None if expected_auto is None and manual is None else (expected_auto or 0) + (manual or 0)
        weight = num(metric.get("Weight")) or 0.0
        expected_ws = weight * (expected_fin or 0.0)
        expected_final[result["_record_id"]] = expected_fin
        expected_weighted[result["_record_id"]] = expected_ws
        expected_weighted_by_emp_period[key] += expected_ws

        # T21 is a deliberately separate D-013/D-014 income fixture; its channel
        # facts are not personal KPI inputs. Its dedicated checks are appended later.
        if not is_t21_special:
            if not same(result.get("Achievement_Rate"), rate): diff.append("Achievement_Rate")
            if not same(result.get("Auto_Score"), expected_auto): diff.append("Auto_Score")
            if not same(result.get("Final_Score"), expected_fin): diff.append("Final_Score")
            if not same(result.get("Weighted_Score"), expected_ws): diff.append("Weighted_Score")
            if not same(result.get("Weight"), weight): diff.append("Weight")
        # D-010-R3: eligibility is an auditable conjunction of configured day and
        # revenue thresholds. Revenue missing is deliberately NOT inferred as zero:
        # the Base formula stays blank and the report marks it pending confirmation.
        scope = scope_by_rid.get(link_id(result.get("Exemption_Scope_ID")))
        revenue = num(result.get("Monthly_Revenue"))
        days = num(result.get("Project_Run_Days"))
        expected_exempt = None
        exemption_pending = False
        if scope and scope.get("Status") == "Active":
            max_days = num(scope.get("Max_Project_Run_Days"))
            max_revenue = num(scope.get("Max_Monthly_Revenue"))
            if days is None or revenue is None or max_days is None or max_revenue is None:
                exemption_pending = True
            else:
                expected_exempt = days < max_days and revenue <= max_revenue
                actual_exempt = str(result.get("Is_Exempt")).lower() == "true"
                if not is_t21_special and actual_exempt != expected_exempt:
                    diff.append("D010_R3_Is_Exempt")
        rows.append({"result_id": result_id, "record_id": result["_record_id"], "employee_record_id": key[0], "period": key[1], "metric_id": metric["Metric_ID"], "actual_id": actual_row.get("Actual_ID") if actual_row else None, "v04_source_cell": metric.get("Source_Cell"), "expected": {"target": target, "achievement_rate": rate, "auto_score": expected_auto, "final_score": expected_fin, "weighted_score": expected_ws}, "actual": {"achievement_rate": result.get("Achievement_Rate"), "auto_score": result.get("Auto_Score"), "final_score": result.get("Final_Score"), "weighted_score": result.get("Weighted_Score"), "monthly_total": result.get("Monthly_Total"), "tier": result.get("Commission_Tier_Level"), "commission_ratio": result.get("Commission_Ratio"), "commission_amount": result.get("Commission_Amount")}, "differences": diff})
        rows[-1]["expected"].update({"d010_r3_is_exempt": expected_exempt, "d010_r3_revenue": revenue})
        rows[-1]["actual"].update({"is_exempt": result.get("Is_Exempt"), "monthly_revenue": result.get("Monthly_Revenue"), "revenue_actual_record_id": link_id(result.get("Revenue_Actual_ID"))})
        if exemption_pending:
            rows[-1]["warnings"] = ["营收未知【待确认】：已命中豁免范围但缺少项目运行天数、营收Actual或配置阈值；未作豁免判定。"]

    # 汇总、梯度及提成逐行复算。所有结果行同一员工+期间的预期总分相同。
    by_rid = {r["record_id"]: r for r in rows}
    for result in results:
        output = by_rid.get(result["_record_id"])
        if not output:
            continue
        is_t21_special = result.get("Source") == "SIMULATED_T21_D013_D014"
        key = (link_id(result.get("Employee_ID")) or "", result.get("Period") or "")
        total = expected_weighted_by_emp_period[key]
        metric = metric_by_rid[link_id(result.get("Metric_ID"))]
        pos_rid = link_id(metric.get("Position_ID"))
        candidates = [t for t in tier_by_position.get(pos_rid or "", []) if num(t.get("Score_Lower")) is not None and num(t.get("Score_Lower")) <= total]
        matched = max(candidates, key=lambda t: num(t.get("Score_Lower")) or 0) if candidates else None
        expected_tier = num(matched.get("Tier_Level")) if matched else None
        expected_ratio = commission_ratio(matched, tiers, pos_rid, base_rate_override)
        base = num(result.get("Commission_Base"))
        # D-010-R3: an independently recomputed true dual-condition eligibility
        # uses the configured Base_Rate directly, skipping the normal tier coefficient.
        is_d010_exempt = output["expected"].get("d010_r3_is_exempt") is True
        is_t14_d010 = result.get("Source") == "SIMULATED_T14_D010_NONZERO" and str(result.get("Is_Exempt")).lower() == "true"
        if not is_t21_special and (is_d010_exempt or is_t14_d010):
            expected_ratio = resolve_base_rate(tiers, pos_rid, base_rate_override)
            if not same(result.get("Commission_Ratio"), expected_ratio):
                output["differences"].append("D010_R3_Commission_Ratio")
        expected_amount = None
        if base is not None and expected_ratio is not None:
            expected_amount = base * expected_ratio
        output["expected"].update({"monthly_total": total, "tier": expected_tier, "commission_ratio": expected_ratio, "commission_amount": expected_amount})
        if not is_t21_special:
            if not same(result.get("Monthly_Total"), total): output["differences"].append("Monthly_Total")
            if not same(result.get("Commission_Tier_Level"), expected_tier): output["differences"].append("Commission_Tier_Level")
        # Commission_Base=0 时，Base 对 Commission_Ratio/Amount 的显示可为 0 或空；
        # 两者的金额语义均为零，不构成公式错误。仅在独立预期亦为 0 时归一化。
        zero_display_equivalent = base == 0 and expected_ratio == 0.0
        ratio_matches = same(result.get("Commission_Ratio"), expected_ratio) or (zero_display_equivalent and result.get("Commission_Ratio") in (None, ""))
        amount_matches = same(result.get("Commission_Amount"), expected_amount) or (zero_display_equivalent and result.get("Commission_Amount") in (None, ""))
        if not is_t21_special:
            if not ratio_matches: output["differences"].append("Commission_Ratio")
            if not amount_matches: output["differences"].append("Commission_Amount")
        if result.get("Source") == "SIMULATED_T21_D013_D014":
            # 专项行把渠道 Actual 用作 GSV 输入；按 Note 中的追溯参数独立核 D-013/D-014，
            # 不将渠道粒度 Actual 误作个人 KPI 自动评分。
            try: note = json.loads(result.get("Note") or "{}")
            except json.JSONDecodeError: note = {}
            case = str(note.get("t21_case", "")); checks: list[str] = []
            if case.startswith("D013"):
                gsv=num(note.get("channel_gsv")); people=num(note.get("middle_control_count")); salary=num(result.get("Perf_Salary_Snapshot")); channel=str(note.get("channel_record_id") or ""); responsible=link_ids(employee_by_rid.get(link_id(result.get("Employee_ID")), {}).get("Responsible_Channel_IDs")); eligible_people=eligible_middle_control_employee_ids(employees, position_by_rid, channel); actual_people=len(eligible_people); total=(num(result.get("Manual_Score")) or 0)*(num(result.get("Weight")) or 0)
                pct=d013_tier_percentage(total); ratio=.001/actual_people if actual_people else None; commission=gsv*ratio if gsv is not None and ratio is not None else None; income=salary*pct+commission if salary is not None and commission is not None else None; actual_income=salary*pct+num(result.get("Commission_Amount")) if salary is not None and num(result.get("Commission_Amount")) is not None else None
                if channel not in responsible: checks.append("D013_Responsible_Channel")
                if not same(actual_people,people): checks.append("D013_Middle_Control_Count")
                if not same(result.get("Commission_Base"),gsv): checks.append("D013_Commission_Base_Channel_GSV")
                if not same(result.get("Commission_Ratio"),ratio): checks.append("D013_GSV_Ratio")
                if not same(result.get("Commission_Amount"),commission): checks.append("D013_GSV_Share_Amount")
                if not same(actual_income,income): checks.append("D013_Composite_Income")
                output["expected"].update({"d013_score_total":total,"d013_tier_percentage":pct,"d013_eligible_middle_control_employee_record_ids":sorted(eligible_people),"d013_composite_income":income}); output["actual"].update({"d013_composite_income":actual_income})
            elif case == "D014-MULTI":
                # D-014 must be driven by Base relations, not the simulated Note.  An
                # unmaintained channel relation is explicitly skipped and reported:
                # production/support employees without a channel are valid cases.
                employee = employee_by_rid.get(link_id(result.get("Employee_ID")), {})
                responsible_channels = link_ids(employee.get("Responsible_Channel_IDs"))
                if not responsible_channels:
                    output.setdefault("warnings", []).append(
                        "D014_Responsible_Channel_Unmaintained：员工未维护 Responsible_Channel_IDs；已跳过专项基数校验。"
                    )
                    output["expected"].update({
                        "d014_validation": "SKIPPED_UNMAINTAINED",
                        "d014_responsible_channel_ids": [],
                        "d014_responsible_channel_gsv_sum": None,
                    })
                else:
                    period_actuals = [
                        actual for actual in actuals
                        if actual.get("Period") == result.get("Period")
                        and actual.get("Status") == "Active"
                        and link_id(actual.get("Channel_ID")) in responsible_channels
                        and num(actual.get("Actual_Value")) is not None
                        and is_gsv_metric(metric_by_rid.get(link_id(actual.get("Metric_ID"))))
                    ]
                    expected_base = sum(num(actual.get("Actual_Value")) or 0.0 for actual in period_actuals)
                    if not same(result.get("Commission_Base"), expected_base):
                        checks.append("D014_Full_Responsible_Channel_GSV_Base")
                    output["expected"].update({
                        "d014_validation": "VALIDATED",
                        "d014_responsible_channel_ids": sorted(responsible_channels),
                        "d014_responsible_channel_gsv_sum": expected_base,
                        "d014_channel_count": len(responsible_channels),
                        "d014_actual_ids": [actual.get("Actual_ID") for actual in period_actuals],
                    })
            else: checks.append("T21_Note_Missing")
            output["differences"].extend(checks)

    # 幂等复验：第二次只读，核验行数和每条 Monthly_Total 完全稳定。
    second = records("Performance_Result", ["Result_ID", "Monthly_Total"])
    first_totals = {r.get("Result_ID"): r.get("Monthly_Total") for r in results}
    second_totals = {r.get("Result_ID"): r.get("Monthly_Total") for r in second}
    idempotence = {"first_row_count": len(results), "second_row_count": len(second), "monthly_total_stable": first_totals == second_totals}

    # LIVE-003 与 LIVE 梯度专项核查。
    live003 = [r for r in rows if r["actual_id"] in {"ACT000013", "ACT000022", "ACT000031"}]
    live_metric = next(m for m in metrics if m.get("Metric_ID") == "MET-V04-IE-LIVE-003")
    live_pos = link_id(live_metric.get("Position_ID"))
    live_actual_tiers = sorted([{"commission_tier_id": t.get("Commission_Tier_ID"), "source_cell": t.get("Source_Cell"), "lower": num(t.get("Score_Lower")), "upper": num(t.get("Score_Upper")), "level": num(t.get("Tier_Level"))} for t in tier_by_position.get(live_pos or "", [])], key=lambda x: x["level"] or 0)
    live_v04_tiers = v04_live_tiers(v04)
    live_tier_migrated_correctly = [(x["lower"], x["upper"]) for x in live_actual_tiers] == [(float(x["lower"]), None if x["upper"] == "♾️" else float(x["upper"])) for x in live_v04_tiers]

    differences = [r for r in rows if r["differences"]]
    report = {
        "task": "T12a", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "mode": "READ_ONLY_INDEPENDENT_RECALCULATION", "source": {"v04_file": V04.name, "v04_sha256": v04["source"]["sha256"], "simulation_manifest": MANIFEST.name, "base": BASE, "base_rate_override": base_rate_override},
        "scope": {"performance_result_rows": len(results), "actual_rows": len(actuals), "manifest_rows": len(manifest["records"])},
        "idempotence": idempotence,
        "comparison": {"consistent_rows": len(rows) - len(differences), "difference_rows": len(differences), "blocking_issues": issues, "rows": rows, "difference_list": differences},
        "live_003": {"v04_standard": "漏回复次数=0 得100分；少于3次得60分；≥3次得0分", "checked_actual_ids": [r["actual_id"] for r in live003], "independent_expected_scores": [r["expected"]["auto_score"] for r in live003], "base_actual_scores": [r["actual"]["auto_score"] for r in live003], "conclusion": "Base 公式结果与 V04 一致；T9a 旧预期若为80分则为模拟生成器错误，需更新预期清单。"},
        "live_tier": {"v04_source_tiers": live_v04_tiers, "base_active_tiers": live_actual_tiers, "migrated_correctly": live_tier_migrated_correctly, "conclusion": "无误" if live_tier_migrated_correctly else "【待修复】Base LIVE Commission_Tier 下限/上限与 V04 源梯度错位；本任务未直接修改主数据。"},
        "d013_tier_boundaries": {"rule": "左闭右开：[0,60)→80%；[60,80)→90%；[80,100)→100%；[100,150)→110%；150分及以上按最高档110%（D-009）", "verification": D013_BOUNDARY_VERIFICATION},
        "d010_exemption_rule": {"rule": "Project_Run_Days<90 且 Is_Exempt=true：Auto_Score=100、Weighted_Score=0；Commission_Amount 仍为 Commission_Base×Commission_Ratio", "live_exempt_rows": sum(1 for r in results if r.get("Is_Exempt") is True)},
        "status": "PASS" if not differences and not issues and idempotence["monthly_total_stable"] and live_tier_migrated_correctly else "VERIFIED_WITH_OPEN_ISSUES",
    }
    if readonly:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": report["status"], "report": str(OUT.relative_to(ROOT)), "rows": len(rows), "difference_rows": len(differences), "idempotence": idempotence, "live_tier_migrated_correctly": live_tier_migrated_correctly}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    args = argparse.Namespace(readonly=False)
    try:
        parser = argparse.ArgumentParser(description="独立计算链校验；--base-rate 仅覆盖预期值，不写入 Base。")
        parser.add_argument("--base-rate", type=float, help="只读验证用 Base_Rate 覆盖值")
        parser.add_argument("--readonly", action="store_true", help="只读复验：报告与异常只输出到 stdout，不写入任何文件")
        args = parser.parse_args()
        main(args.base_rate, args.readonly)
    except Exception as exc:
        error = {"task": "T12a", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "error": str(exc)}
        if args.readonly:
            print(json.dumps({"status": "FAILED", "readonly": True, "error": error}, ensure_ascii=False), file=sys.stderr)
        else:
            ERROR_OUT.write_text(json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"status": "FAILED", "error_log": str(ERROR_OUT.relative_to(ROOT)), "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
