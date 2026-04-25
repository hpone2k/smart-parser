"""
Synthetic tool log generator for Micron AISG challenge demo.
Generates realistic semiconductor tool logs in all required formats.
"""
import json
import xml.etree.ElementTree as ET
import csv
import io
import random
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "logs"


def random_timestamp(base=None, offset_seconds=None):
    if base is None:
        base = datetime(2024, 4, 15, 12, 0, 0)
    if offset_seconds is None:
        offset_seconds = random.randint(0, 3600)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%S")


def generate_json_log():
    data = {
        "ControlJob": {
            "CtrlJobID": "CJOB_0001",
            "EquipmentID": "EQP_DRY_ETCH_001",
            "ProcessJobs": [
                {
                    "PRJobID": "PRJOB_0001",
                    "LotID": "LOT_0001",
                    "RecipeStartTime": random_timestamp(),
                    "ModuleProcessReports": [
                        {
                            "Keys": {
                                "ModuleID": "MOD_0001",
                                "RecipeStepID": "RCP_STEP_01",
                                "WaferID": f"WFR_{i:04d}"
                            },
                            "Attributes": {
                                "Events": {
                                    "ControlStateEvents": [
                                        {
                                            "EventID": random.randint(100, 999),
                                            "Text": random.choice([
                                                "Recipe prerequisites started",
                                                "Chamber purge initiated",
                                                "Process step complete",
                                                "Wafer transfer in progress"
                                            ]),
                                            "DateTime": random_timestamp(offset_seconds=i * 60)
                                        }
                                    ],
                                    "Alarms": [] if i % 3 != 0 else [
                                        {"Code": "ALM_001", "Text": "Pressure deviation detected"}
                                    ],
                                    "Errors": []
                                }
                            },
                            "SensorData": [
                                {
                                    "SensorID": f"SENSOR_{j:04d}",
                                    "Measurements": [
                                        {
                                            "DateTime": random_timestamp(offset_seconds=i * 60 + j * 10),
                                            "Value": round(
                                                random.uniform(0.5, 1.5) if j == 0
                                                else random.uniform(80, 95), 3
                                            )
                                        }
                                        for _ in range(3)
                                    ]
                                }
                                for j in range(3)
                            ]
                        }
                        for i in range(5)
                    ]
                }
            ]
        }
    }
    path = OUTPUT_DIR / "dry_etch_vendor_a.json"
    path.write_text(json.dumps(data, indent=2))
    print(f"Generated: {path}")


def generate_xml_log():
    xml_content = """<?xml version='1.0' encoding='UTF-8'?>
<ADELdr:Recipe xmlns:ADELdr="http://www.asml.com/XMLSchema/MT/Generic/ADELdr/v1.5">
  <Header>
    <Title>Dose Recipe</Title>
    <MachineID>MCH_0001</MachineID>
    <MachineCustomerName>CUST_0001</MachineCustomerName>
    <MachineType>MTYPE_EUV_001</MachineType>
    <SoftwareRelease>6.3.0</SoftwareRelease>
    <CreatedBy>CREATOR_0001</CreatedBy>
    <CreateTime>2025-01-01T00:00:00.000+00:00</CreateTime>
    <DocumentId>DOC_0001</DocumentId>
    <DocumentType>ADELdr</DocumentType>
    <DocumentTypeVersion>v1.5</DocumentTypeVersion>
  </Header>
  <RecipeName>RCP_0001</RecipeName>
  <ApprovedBy>CREATOR_0002</ApprovedBy>
  <ExpirationTime>2039-02-09T09:00:31+00:00</ExpirationTime>
  <TargetMachineID>MCH_0001</TargetMachineID>
  <ProcessEvents>
    <Event timestamp="2025-01-01T00:00:00.1417" type="SYSTEM_EVENT" code="ER-4102">
      <Description>DEFAULT log file rotation triggered</Description>
      <Severity>INFO</Severity>
    </Event>
    <Event timestamp="2025-01-01T00:00:00.2013" type="SYSTEM_WARNING" code="DW-20E2">
      <Description>Scan time too short for OASIS light measurement. Current: 15.00ms, Required: 25.00ms</Description>
      <Severity>WARNING</Severity>
      <Parameter name="CurrentScanTime" unit="ms">15.00</Parameter>
      <Parameter name="RequiredScanTime" unit="ms">25.00</Parameter>
    </Event>
    <Event timestamp="2025-01-01T00:00:00.3510" type="PROCESS_STEP" code="PS-001">
      <Description>Exposure sequence initiated on wafer slot 1</Description>
      <Severity>INFO</Severity>
      <Parameter name="DoseTarget" unit="mJ/cm2">28.5</Parameter>
      <Parameter name="FocusOffset" unit="nm">-5.0</Parameter>
      <Parameter name="WaferSlot">1</Parameter>
    </Event>
  </ProcessEvents>
  <SlitProfileList>
    <elt>
      <SlitProfileId>slitProfile_1</SlitProfileId>
      <SlitProfile>
        <LegendreCoefficients>
          <elt><SetPoint>0.000</SetPoint></elt>
          <elt><SetPoint>0.000</SetPoint></elt>
          <elt><SetPoint>0.000</SetPoint></elt>
        </LegendreCoefficients>
      </SlitProfile>
    </elt>
  </SlitProfileList>
</ADELdr:Recipe>"""
    path = OUTPUT_DIR / "euv_scanner_recipe.xml"
    path.write_text(xml_content)
    print(f"Generated: {path}")


def generate_csv_log():
    rows = [["timestamp", "tool_id", "chamber", "parameter", "value", "unit", "status"]]
    base = datetime(2024, 4, 15, 12, 0, 0)
    tools = ["EQP_CMP_001", "EQP_CMP_002"]
    params = [
        ("Temperature", 80, 95, "C"),
        ("Pressure", 0.8, 1.2, "Pa"),
        ("RF_Power", 140, 160, "W"),
        ("Flow_Rate", 45, 55, "sccm"),
        ("Rotation_Speed", 28, 32, "rpm"),
    ]
    for i in range(30):
        ts = (base + timedelta(seconds=i * 30)).strftime("%Y-%m-%d %H:%M:%S")
        tool = random.choice(tools)
        param, lo, hi, unit = random.choice(params)
        value = round(random.uniform(lo, hi), 2)
        status = "NORMAL" if random.random() > 0.1 else "WARNING"
        rows.append([ts, tool, f"C{random.randint(1, 4)}", param, value, unit, status])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(rows)
    path = OUTPUT_DIR / "cmp_sensor_trace.csv"
    path.write_text(output.getvalue())
    print(f"Generated: {path}")


def generate_text_log():
    lines = [
        "2024-04-15 12:03:20 [INFO]  TOOL=EQP_ETCH_002 TEMP=85.2C PRESSURE=0.9Pa RF_POWER=150W STATUS=PROCESSING",
        "2024-04-15 12:04:01 [INFO]  TOOL=EQP_ETCH_002 STEP=3 ETCH_TIME=120s RF_POWER=150W GAS_FLOW=50sccm",
        "2024-04-15 12:05:47 [ERROR] TOOL=EQP_ETCH_002 ALARM: VACUUM_FAULT - Chamber pressure exceeded threshold (1.5Pa > 1.2Pa limit)",
        "2024-04-15 12:05:48 [WARN]  TOOL=EQP_ETCH_002 Auto-recovery initiated. Purge cycle starting.",
        "2024-04-15 12:06:15 [INFO]  TOOL=EQP_ETCH_002 STEP=3 resumed after recovery. ETCH_TIME=85s remaining.",
        "2024-04-15 12:07:30 [INFO]  TOOL=EQP_ETCH_002 TEMP=84.8C PRESSURE=0.91Pa RF_POWER=148W STATUS=PROCESSING",
        "2024-04-15 12:09:00 [INFO]  TOOL=EQP_ETCH_002 STEP=3 complete. Transitioning to STEP=4.",
        "2024-04-15 12:09:02 [INFO]  TOOL=EQP_ETCH_002 STEP=4 DEPOSITION_TIME=60s TEMP_TARGET=90C",
        "2024-04-15 12:10:15 [WARN]  TOOL=EQP_ETCH_002 TEMP=92.1C - Approaching upper threshold (95C). Monitor required.",
        "2024-04-15 12:11:00 [INFO]  TOOL=EQP_ETCH_002 STEP=4 complete. Wafer WFR_0042 processing done.",
        "2024-04-15 12:11:05 [INFO]  TOOL=EQP_ETCH_002 Initiating wafer transfer to cooling station.",
    ]
    path = OUTPUT_DIR / "etch_event_log.txt"
    path.write_text("\n".join(lines))
    print(f"Generated: {path}")


def generate_syslog():
    lines = [
        "Apr 15 12:00:01 MCH0001 kernel: [tool_driver] EQP_CVD_001 initialized, firmware v3.2.1",
        "Apr 15 12:00:05 MCH0001 tool_svc[1234]: Chamber A purge sequence started",
        "Apr 15 12:01:10 MCH0001 tool_svc[1234]: SENSOR_OK temp_sensor_01=83.4C (range: 70-100C)",
        "Apr 15 12:01:10 MCH0001 tool_svc[1234]: SENSOR_OK pressure_sensor_01=0.88Pa (range: 0.5-1.5Pa)",
        "Apr 15 12:02:30 MCH0001 tool_svc[1234]: RECIPE_LOAD RCP_CVD_NITRIDE_001 loaded, steps=6",
        "Apr 15 12:03:00 MCH0001 tool_svc[1234]: STEP_START step=1 name=Preheat target_temp=85C duration=180s",
        "Apr 15 12:06:01 MCH0001 tool_svc[1234]: STEP_COMPLETE step=1 actual_temp=84.9C elapsed=181s",
        "Apr 15 12:06:02 MCH0001 tool_svc[1234]: STEP_START step=2 name=Deposition gas=SiH4 flow=48sccm",
        "Apr 15 12:06:45 MCH0001 tool_svc[1234]: WARNING flow_controller_02: SiH4 flow deviation +3.2sccm",
        "Apr 15 12:07:00 MCH0001 tool_svc[1234]: ALARM CRITICAL plasma_stability: RF match network fault",
        "Apr 15 12:07:01 MCH0001 tool_svc[1234]: EMERGENCY_STOP triggered by safety interlock",
        "Apr 15 12:07:05 MCH0001 tool_svc[1234]: Incident report generated: INC_20240415_001",
    ]
    path = OUTPUT_DIR / "cvd_syslog.log"
    path.write_text("\n".join(lines))
    print(f"Generated: {path}")


def generate_keyvalue_log():
    lines = [
        "DATE=2024-04-15 TIME=13:00:00 EQUIP_ID=EQP_IMP_001 EVENT=SESSION_START",
        "DATE=2024-04-15 TIME=13:00:05 EQUIP_ID=EQP_IMP_001 LOT_ID=LOT_2042 WAFER_ID=WFR_0010 RECIPE=IMP_BORON_001",
        "DATE=2024-04-15 TIME=13:00:10 EQUIP_ID=EQP_IMP_001 STEP=1 BEAM_ENERGY=80keV DOSE=1.2E14 TILT_ANGLE=7deg",
        "DATE=2024-04-15 TIME=13:00:30 EQUIP_ID=EQP_IMP_001 SENSOR=BEAM_CURRENT VALUE=4.52mA STATUS=NORMAL",
        "DATE=2024-04-15 TIME=13:00:30 EQUIP_ID=EQP_IMP_001 SENSOR=VACUUM_LEVEL VALUE=2.1E-7Torr STATUS=NORMAL",
        "DATE=2024-04-15 TIME=13:01:00 EQUIP_ID=EQP_IMP_001 ALARM_CODE=ALM_042 ALARM_MSG=DOSE_DEVIATION SEVERITY=WARNING",
        "DATE=2024-04-15 TIME=13:01:05 EQUIP_ID=EQP_IMP_001 CORRECTIVE_ACTION=BEAM_TUNE_AUTO STATUS=APPLIED",
        "DATE=2024-04-15 TIME=13:02:00 EQUIP_ID=EQP_IMP_001 STEP=1 STATUS=COMPLETE ACTUAL_DOSE=1.199E14 UNIFORMITY=98.7%",
        "DATE=2024-04-15 TIME=13:02:05 EQUIP_ID=EQP_IMP_001 STEP=2 BEAM_ENERGY=80keV DOSE=1.2E14 TILT_ANGLE=-7deg",
        "DATE=2024-04-15 TIME=13:04:00 EQUIP_ID=EQP_IMP_001 STEP=2 STATUS=COMPLETE ACTUAL_DOSE=1.201E14 UNIFORMITY=99.1%",
        "DATE=2024-04-15 TIME=13:04:10 EQUIP_ID=EQP_IMP_001 EVENT=SESSION_END LOT_ID=LOT_2042 WAFER_ID=WFR_0010 RESULT=PASS",
    ]
    path = OUTPUT_DIR / "implant_kv_log.log"
    path.write_text("\n".join(lines))
    print(f"Generated: {path}")


def generate_binary_log():
    header = bytes([0x4D, 0x49, 0x43, 0x52, 0x4F, 0x4E])
    version = bytes([0x01, 0x00])
    tool_id = b'EQP_BIN_001\x00'
    sensor_data = bytes([
        0x42, 0xAA, 0x66, 0x66,
        0x3F, 0x66, 0x66, 0x66,
        0x43, 0x16, 0x00, 0x00,
        0xFF, 0x01, 0x00, 0x00,
    ])
    alarm_text = b'VACUUM_FAULT\x00'
    padding = bytes(16)

    binary_content = header + version + tool_id + sensor_data + alarm_text + padding
    hex_content = binary_content.hex()

    lines = []
    for i in range(0, len(hex_content), 32):
        offset = i // 2
        chunk = hex_content[i:i + 32]
        formatted = ' '.join(chunk[j:j + 2] for j in range(0, len(chunk), 2))
        lines.append(f"{offset:08X}  {formatted}")

    path = OUTPUT_DIR / "diagnostic_binary.bin"
    path.write_text("\n".join(lines))
    print(f"Generated: {path}")


def generate_all():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_json_log()
    generate_xml_log()
    generate_csv_log()
    generate_text_log()
    generate_syslog()
    generate_keyvalue_log()
    generate_binary_log()
    print("\nAll synthetic logs generated!")


if __name__ == "__main__":
    generate_all()
