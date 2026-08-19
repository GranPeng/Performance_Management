import importlib.util
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "verify_calculation_chain.py"
sys.path.insert(0, str(SCRIPTS_DIR))
spec = importlib.util.spec_from_file_location("verify_calculation_chain", MODULE_PATH)
assert spec is not None and spec.loader is not None
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def test_middle_control_count_requires_active_eligible_position_and_employment_status():
    positions = {
        "pos-live": {"Position_Name": "直播中控/运营助理"},
        "pos-assistant": {"Position_Name": "运营助理"},
        "pos-ops": {"Position_Name": "兴趣电商运营"},
    }
    employees = [
        {"_record_id": "emp-live", "Employee_ID": "eligible-live", "Position_ID": [{"id": "pos-live"}], "Status": "Active", "Employment_Status": "在职", "Responsible_Channel_IDs": [{"id": "channel-a"}]},
        {"_record_id": "emp-assistant", "Employee_ID": "eligible-assistant", "Position_ID": [{"id": "pos-assistant"}], "Status": "正式在岗", "Employment_Status": "正式在岗", "Responsible_Channel_IDs": [{"id": "channel-a"}]},
        {"_record_id": "emp-inactive", "Employee_ID": "inactive", "Position_ID": [{"id": "pos-live"}], "Status": "Inactive", "Employment_Status": "在职", "Responsible_Channel_IDs": [{"id": "channel-a"}]},
        {"_record_id": "emp-terminated", "Employee_ID": "terminated", "Position_ID": [{"id": "pos-live"}], "Status": "Active", "Employment_Status": "离职", "Responsible_Channel_IDs": [{"id": "channel-a"}]},
        {"_record_id": "emp-non-control", "Employee_ID": "non-control", "Position_ID": [{"id": "pos-ops"}], "Status": "Active", "Employment_Status": "在职", "Responsible_Channel_IDs": [{"id": "channel-a"}]},
    ]

    assert verify.count_eligible_middle_controls(employees, positions, "channel-a") == 2


def test_gsv_metric_classifier_excludes_roi_consumption_and_conversion():
    assert verify.is_gsv_metric({"Metric_Name": "团队退货后GSV达成率"})
    assert verify.is_gsv_metric({"Metric_Name": "团队营收目标达成率"})
    assert not verify.is_gsv_metric({"Metric_Name": "主播ROI达成率"})
    assert not verify.is_gsv_metric({"Metric_Name": "广告消耗达成率"})
    assert not verify.is_gsv_metric({"Metric_Name": "转化次数"})
