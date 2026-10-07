#!/usr/bin/env python3
"""Generate the SYNTHETIC Body Domain Controller (BDC) HLD documents (v1.0, v1.1) and all ground-truth files.

No real OEM / AUTOSAR-consortium text is used: every sentence below is original, fictional content created for
academic evaluation. Run:  python Code/scripts/generate_synthetic_hld.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Code" / "src"))
from hldrag.compare import compare_kbs  # noqa: E402

OUT = ROOT / "Input_Data"
GT = OUT / "ground_truth"


def build_model(version):
    v11 = version == "1.1"
    thr = 20 if v11 else 15
    comps = [
        ("SWC_DoorLockMgr", "Application", "Central locking state machine and lock arbitration", [
            "SWC_DoorLockMgr implements the central locking state machine with the states LOCKED, UNLOCKED and SUPERLOCKED.",
            "It arbitrates lock and unlock requests from SWC_KeyFobHandler and from the auto-lock function.",
            f"Auto-lock is triggered when VehicleSpeed exceeds {thr} km/h while any door is unlocked.",
            "The component persists the last lock state through SWC_NvmManager every time the state changes.",
            "Runnable DoorLockMgr_Run10ms executes every 10 ms."]),
        ("SWC_KeyFobHandler", "Application", "Remote key fob command decoding and validation", [
            "SWC_KeyFobHandler decodes remote key fob commands received on the CAN message KeyFob_Cmd.",
            "It validates the rolling-code counter supplied by the immobilizer and discards commands with an invalid counter.",
            "Valid commands are forwarded to SWC_DoorLockMgr as KeyFobCmd.",
            "Runnable KeyFobHandler_Run20ms executes every 20 ms."]),
        ("SWC_WindowCtrl", "Application", "Power window control with anti-pinch protection", [
            "SWC_WindowCtrl controls the four power windows including one-touch up and down movement.",
            "Anti-pinch protection stops and reverses the window within 50 ms of pinch detection.",
            "The comfort-close function raises all windows when the vehicle is locked with the key fob held for more than 2 seconds, using DoorLockState from SWC_DoorLockMgr.",
            "The window position is transmitted as WindowPosition.",
            "Runnable WindowCtrl_Run10ms executes every 10 ms."]),
        ("SWC_LightingCtrl", "Application", "Exterior lighting and courtesy lamp control", [
            "SWC_LightingCtrl controls the exterior lighting: low beam, high beam, turn indicators and the courtesy lamp.",
            "The courtesy lamp is switched on for 30 seconds when SWC_DoorLockMgr reports an unlocked state.",
            "Turn indicators flash at 1.5 Hz.",
            "The component requires VehicleSpeed to enable the speed-dependent cornering lamp.",
            "Runnable LightingCtrl_Run50ms executes every 50 ms."]),
        ("SWC_VehicleSpeedProv", "Application", "Filtered vehicle speed provider", [
            "SWC_VehicleSpeedProv provides the filtered vehicle speed derived from the wheel-speed message VehSpd_ESC received from the ESC ECU.",
            "The value is a 16-bit unsigned integer with a resolution of 0.01 km/h.",
            "Signals with a failed CRC are replaced by the last valid value for up to 100 ms, after which the output is flagged invalid.",
            "Runnable VehSpeedProv_Run20ms executes every 20 ms."]),
        ("SWC_DiagHandler", "Service", "UDS diagnostic request routing", [
            "SWC_DiagHandler routes UDS diagnostic requests received from the diagnostic communication manager to the owning component.",
            "It supports the services ReadDataByIdentifier (0x22) and WriteDataByIdentifier (0x2E) for the data identifiers defined in Section 4.3.",
            "Requests for unsupported identifiers are answered with negative response code (NRC) 0x31.",
            "The component is event-triggered and has no cyclic runnable."]),
        ("SWC_NvmManager", "Service", "Non-volatile memory access service", [
            "SWC_NvmManager provides non-volatile storage services through the client-server interface If_NvmAccess.",
            "It manages three NVM blocks: LockStateBlock (4 bytes), WindowCalibBlock (16 bytes) and DtcBlock (64 bytes).",
            "Writes are queued and executed asynchronously by the memory stack; a write completes within 20 ms under normal conditions."]),
    ]
    ports = [
        ("SWC_KeyFobHandler", "PP_KeyFobCmd", "P-Port", "If_KeyFobCmd"),
        ("SWC_DoorLockMgr", "RP_KeyFobCmd", "R-Port", "If_KeyFobCmd"),
        ("SWC_DoorLockMgr", "RP_VehicleSpeed", "R-Port", "If_VehicleSpeed"),
        ("SWC_DoorLockMgr", "PP_DoorState", "P-Port", "If_DoorState"),
        ("SWC_DoorLockMgr", "RP_NvmAccess", "R-Port", "If_NvmAccess"),
        ("SWC_DoorLockMgr", "PP_DiagData", "P-Port", "If_DiagData"),
        ("SWC_WindowCtrl", "RP_DoorState", "R-Port", "If_DoorState"),
        ("SWC_WindowCtrl", "PP_WindowPos", "P-Port", "If_WindowPos"),
        ("SWC_WindowCtrl", "RP_NvmAccess", "R-Port", "If_NvmAccess"),
        ("SWC_WindowCtrl", "PP_DiagData", "P-Port", "If_DiagData"),
        ("SWC_LightingCtrl", "RP_DoorState", "R-Port", "If_DoorState"),
        ("SWC_LightingCtrl", "RP_VehicleSpeed", "R-Port", "If_VehicleSpeed"),
        ("SWC_LightingCtrl", "PP_LampCmd", "P-Port", "If_LampCmd"),
        ("SWC_VehicleSpeedProv", "PP_VehicleSpeed", "P-Port", "If_VehicleSpeed"),
        ("SWC_DiagHandler", "RP_DiagDoor", "R-Port", "If_DiagData"),
        ("SWC_DiagHandler", "RP_DiagWindow", "R-Port", "If_DiagData"),
        ("SWC_NvmManager", "PP_NvmAccess", "P-Port", "If_NvmAccess"),
    ]
    interfaces = [
        ("If_KeyFobCmd", "Sender-Receiver", "KeyFobCmd", "uint8"),
        ("If_VehicleSpeed", "Sender-Receiver", "VehicleSpeed", "uint16"),
        ("If_DoorState", "Sender-Receiver", "DoorLockState", "uint8"),
        ("If_WindowPos", "Sender-Receiver", "WindowPosition", "uint8"),
        ("If_LampCmd", "Sender-Receiver", "LampCmd", "uint8"),
        ("If_NvmAccess", "Client-Server", "ReadBlock", "Std_ReturnType"),
        ("If_NvmAccess", "Client-Server", "WriteBlock", "Std_ReturnType"),
        ("If_DiagData", "Client-Server", "ReadDid", "Std_ReturnType"),
        ("If_DiagData", "Client-Server", "WriteDid", "Std_ReturnType"),
    ]
    signals = [
        ("KeyFobCmd", "KeyFob_Cmd", "0x2A0", 8, "Rx", "Event", "SWC_KeyFobHandler.PP_KeyFobCmd"),
        ("VehicleSpeed", "VehSpd_ESC", "0x1F0", 16 if v11 else 8, "Rx", "20", "SWC_VehicleSpeedProv.PP_VehicleSpeed"),
        ("DoorLockState", "BDC_Status", "0x3B0", 8, "Tx", "100", "SWC_DoorLockMgr.PP_DoorState"),
        ("WindowPosition", "BDC_Window", "0x3B1", 8, "Tx", "100", "SWC_WindowCtrl.PP_WindowPos"),
        ("LampCmd", "BDC_Lamp", "0x3B2", 8, "Tx", "50", "SWC_LightingCtrl.PP_LampCmd"),
    ]
    conns = [
        ("SWC_KeyFobHandler.PP_KeyFobCmd", "SWC_DoorLockMgr.RP_KeyFobCmd", "Forward validated remote commands"),
        ("SWC_VehicleSpeedProv.PP_VehicleSpeed", "SWC_DoorLockMgr.RP_VehicleSpeed", "Auto-lock threshold evaluation"),
        ("SWC_DoorLockMgr.PP_DoorState", "SWC_WindowCtrl.RP_DoorState", "Comfort close"),
        ("SWC_DoorLockMgr.PP_DoorState", "SWC_LightingCtrl.RP_DoorState", "Courtesy lamp control"),
        ("SWC_NvmManager.PP_NvmAccess", "SWC_DoorLockMgr.RP_NvmAccess", "Persist lock state"),
        ("SWC_NvmManager.PP_NvmAccess", "SWC_WindowCtrl.RP_NvmAccess", "Persist window calibration"),
        ("SWC_DoorLockMgr.PP_DiagData", "SWC_DiagHandler.RP_DiagDoor", "Diagnostic data access to door lock data"),
        ("SWC_WindowCtrl.PP_DiagData", "SWC_DiagHandler.RP_DiagWindow", "Diagnostic data access to window data"),
    ]
    dids = [
        ("0x0100", "DoorLockCounter", "SWC_DoorLockMgr", "2"),
        ("0x0101", "LastLockState", "SWC_DoorLockMgr", "1"),
        ("0x0200", "WindowCalibStatus", "SWC_WindowCtrl", "1"),
    ]
    nfr = [
        ("NFR-01", "Central lock actuation latency from KeyFobCmd reception", "max 100 ms"),
        ("NFR-02", "Anti-pinch reversal time after pinch detection", "max 50 ms"),
        ("NFR-03", "Auto-lock vehicle speed threshold", f"{thr} km/h"),
        ("NFR-04", "NVM write completion time", "max 20 ms"),
        ("NFR-05", "Courtesy lamp on-time after unlock", "30 s"),
        ("NFR-06", "Vehicle speed signal hold time after CRC failure", "max 100 ms"),
    ]
    revisions = [("1.0", "2026-09-15", "Initial release of the BDC high-level design.")]
    flows = {
        "FF-01 Remote Unlock": [
            "The Com stack receives the CAN message KeyFob_Cmd and updates the signal KeyFobCmd.",
            "SWC_KeyFobHandler validates the rolling-code counter and discards invalid commands.",
            "SWC_KeyFobHandler publishes KeyFobCmd with value 2 (unlock) through port PP_KeyFobCmd.",
            "SWC_DoorLockMgr transitions from the state LOCKED to the state UNLOCKED.",
            "SWC_DoorLockMgr writes the new state through SWC_NvmManager.",
            "SWC_DoorLockMgr publishes DoorLockStatus to SWC_WindowCtrl and SWC_LightingCtrl"
            + (" and SWC_MirrorCtrl." if v11 else "."),
            "The Com stack transmits BDC_Status within 100 ms of Step 1."],
        "FF-02 Speed-Dependent Auto-Lock": [
            "SWC_VehicleSpeedProv publishes VehicleSpeed every 20 ms.",
            f"SWC_DoorLockMgr compares VehicleSpeed with the auto-lock threshold of {thr} km/h.",
            "If the threshold is exceeded and any door is unlocked, SWC_DoorLockMgr transitions to the state LOCKED.",
            "SWC_ClimateCtrl is notified to close the air vents.",
            "SWC_DoorLockMgr publishes the new DoorLockState."],
        "FF-03 Window Anti-Pinch Reversal": [
            "SWC_WindowCtrl detects a pinch event from the motor current while a window is closing.",
            "SWC_WindowCtrl stops the motor and reverses the window within 50 ms.",
            "SWC_WindowCtrl publishes the new WindowPosition."],
        "FF-04 Diagnostic Data Read": [
            "A UDS request with service 0x22 for a data identifier is received by SWC_DiagHandler.",
            "SWC_DiagHandler routes the request to the owning component through the port RP_DiagDoor or RP_DiagWindow.",
            "The owning component returns the data and SWC_DiagHandler sends a positive response with service 0x62.",
            "For an unsupported identifier SWC_DiagHandler sends negative response code 0x31."],
    }
    if v11:
        comps.append(("SWC_MirrorCtrl", "Application", "Exterior mirror folding control", [
            "SWC_MirrorCtrl folds the exterior mirrors when the vehicle is locked and unfolds them when the vehicle is unlocked.",
            "A complete fold or unfold movement takes 3 seconds.",
            "The component requires DoorLockState from SWC_DoorLockMgr.",
            "Runnable MirrorCtrl_Run50ms executes every 50 ms."]))
        ports += [("SWC_MirrorCtrl", "RP_DoorState", "R-Port", "If_DoorState"),
                  ("SWC_MirrorCtrl", "PP_MirrorCmd", "P-Port", "If_MirrorCmd")]
        interfaces.append(("If_MirrorCmd", "Sender-Receiver", "MirrorCmd", "uint8"))
        signals.append(("MirrorCmd", "BDC_Mirror", "0x3B3", 8, "Tx", "100", "SWC_MirrorCtrl.PP_MirrorCmd"))
        conns += [("SWC_VehicleSpeedProv.PP_VehicleSpeed", "SWC_LightingCtrl.RP_VehicleSpeed",
                   "Speed-dependent cornering lamp"),
                  ("SWC_DoorLockMgr.PP_DoorState", "SWC_MirrorCtrl.RP_DoorState", "Mirror fold on lock")]
        nfr.append(("NFR-07", "Mirror fold or unfold movement time", "3 s"))
        revisions.append(("1.1", "2026-10-01",
                          "Added SWC_MirrorCtrl, raised the auto-lock threshold to 20 km/h, widened VehicleSpeed to 16 bit "
                          "and connected SWC_LightingCtrl to VehicleSpeed."))
    return dict(version=version, comps=comps, ports=ports, interfaces=interfaces, signals=signals, conns=conns,
                dids=dids, nfr=nfr, revisions=revisions, flows=flows, v11=v11, thr=thr)


def to_kb(m):
    return {
        "doc_id": "BDC-HLD-001", "version": m["version"], "doc_key": f"BDC-HLD-001@{m['version']}",
        "components": [dict(name=a, type=b, responsibility=c) for a, b, c, _ in m["comps"]],
        "ports": [dict(component=a, port=b, direction=c, interface=d) for a, b, c, d in m["ports"]],
        "interfaces": [dict(name=a, kind=b, element=c, datatype=d) for a, b, c, d in m["interfaces"]],
        "signals": [dict(name=a, message=b, can_id=c, length_bits=d, dir=e, cycle=f, mapped_port=g)
                    for a, b, c, d, e, f, g in m["signals"]],
        "connections": [dict(provider=a, requirer=b, purpose=c) for a, b, c in m["conns"]],
        "constraints": [dict(id=a, requirement=b, value=c) for a, b, c in m["nfr"]],
        "dids": [dict(did=a, name=b, owner=c, length=d) for a, b, c, d in m["dids"]],
    }


def seeded_defects(m):
    d = []
    if not m["v11"]:
        d.append({"id": "D1", "rule": "R1", "key": "SWC_LightingCtrl.RP_VehicleSpeed",
                  "description": "Required port has no provider connection"})
        d.append({"id": "D2", "rule": "R2", "key": "VehicleSpeed",
                  "description": "Signal length (8 bit) does not match interface data type uint16"})
    d.append({"id": "D3", "rule": "R3", "key": "SWC_ClimateCtrl",
              "description": "Flow FF-02 references a component missing from the catalogue"})
    d.append({"id": "D4", "rule": "R4", "key": "DoorLockStatus",
              "description": "Terminology inconsistency: DoorLockStatus vs DoorLockState"})
    return d


QA = [  # id, question, must_contain (case-insens. substrings in the answer), evidence (substrings of source chunks), type
    ("Q01", "What does SWC_DoorLockMgr do?", ["central locking", "state machine"], ["central locking state machine"], "fact"),
    ("Q02", "At what vehicle speed does auto-lock trigger?", ["15 km/h"], ["exceeds 15 km/h"], "fact"),
    ("Q03", "Which component provides VehicleSpeed?", ["SWC_VehicleSpeedProv"], ["provides the filtered vehicle speed"], "relation"),
    ("Q04", "What ports does SWC_WindowCtrl have?", ["RP_DoorState", "PP_WindowPos", "RP_NvmAccess", "PP_DiagData"],
     ["component: swc_windowctrl; port:"], "list"),
    ("Q05", "Which components consume DoorLockState?", ["SWC_WindowCtrl", "SWC_LightingCtrl"],
     ["interface: if_doorstate"], "relation"),
    ("Q06", "How fast must the anti-pinch function reverse the window?", ["50 ms"], ["within 50 ms of pinch detection"], "fact"),
    ("Q07", "What is the CAN ID of the BDC_Status message?", ["0x3B0"], ["can message: bdc_status; can id: 0x3b0"], "fact"),
    ("Q08", "What is the cycle time of the VehSpd_ESC message?", ["20"], ["can message: vehspd_esc"], "fact"),
    ("Q09", "How long is the courtesy lamp on after unlock?", ["30"], ["switched on for 30 seconds"], "fact"),
    ("Q10", "Which NVM blocks does SWC_NvmManager manage?", ["LockStateBlock", "WindowCalibBlock", "DtcBlock"],
     ["manages three nvm blocks"], "list"),
    ("Q11", "What NRC is returned for an unsupported data identifier?", ["0x31"], ["negative response code (nrc) 0x31"], "fact"),
    ("Q12", "Which DID is owned by SWC_WindowCtrl?", ["0x0200"], ["owner component: swc_windowctrl"], "fact"),
    ("Q13", "What is the data type of the VehicleSpeed element?", ["uint16"], ["data element / operation: vehiclespeed"], "fact"),
    ("Q14", "What is the resolution of the vehicle speed value?", ["0.01"], ["resolution of 0.01 km/h"], "fact"),
    ("Q15", "Which diagnostic services does SWC_DiagHandler support?", ["0x22", "0x2E"], ["supports the services"], "fact"),
    ("Q16", "What happens when the rolling-code counter is invalid?", ["discard"], ["discards commands with an invalid counter"], "fact"),
    ("Q17", "When does the comfort-close function operate?", ["2 seconds"], ["comfort-close function raises all windows"], "fact"),
    ("Q18", "What is the turn indicator flash frequency?", ["1.5 hz"], ["turn indicators flash at 1.5 hz"], "fact"),
    ("Q19", "How many bytes is the DtcBlock?", ["64"], ["dtcblock (64 bytes)"], "fact"),
    ("Q20", "Which runnable does SWC_KeyFobHandler execute and at what period?", ["KeyFobHandler_Run20ms", "20 ms"],
     ["runnable keyfobhandler_run20ms executes every 20 ms"], "fact"),
    ("Q21", "List the steps of the remote unlock flow.", ["rolling-code", "NvmManager"], ["step 2:"], "flow"),
    ("Q22", "Who is the requirer of SWC_NvmManager.PP_NvmAccess?", ["SWC_DoorLockMgr", "SWC_WindowCtrl"],
     ["provider port: swc_nvmmanager.pp_nvmaccess"], "relation"),
    ("Q23", "What is the maximum latency from key fob command to lock actuation?", ["100 ms"],
     ["central lock actuation latency"], "fact"),
    ("Q24", "How long does an NVM write take to complete?", ["20 ms"], ["a write completes within 20 ms"], "fact"),
    ("Q25", "What happens if the vehicle speed CRC fails?", ["last valid value", "100 ms"], ["failed crc are replaced"], "fact"),
    ("Q26", "What AUTOSAR release is the BDC software based on?", ["R22-11"], ["release r22-11"], "fact"),
    ("Q27", "Which interface type is If_NvmAccess?", ["client-server"], ["interface: if_nvmaccess"], "fact"),
    ("Q28", "Which components does SWC_DoorLockMgr depend on?", ["SWC_KeyFobHandler", "SWC_VehicleSpeedProv", "SWC_NvmManager"],
     ["requirer port: swc_doorlockmgr."], "relation"),
    ("Q29", "Which CAN message carries LampCmd?", ["BDC_Lamp"], ["signal: lampcmd"], "fact"),
    ("Q30", "What is the direction of the KeyFobCmd signal?", ["Rx"], ["signal: keyfobcmd"], "fact"),
    ("Q31", "What is the CAN bit rate used by the BDC?", ["500 kbit/s"], ["bit rate of 500 kbit/s"], "fact"),
]
OOS = [
    ("O01", "What is the maximum torque of the engine in the vehicle?"),
    ("O02", "Who is the CEO of Bosch?"),
    ("O03", "What is the tyre pressure monitoring threshold?"),
    ("O04", "Describe the ADAS lane keeping algorithm."),
    ("O05", "What is the battery capacity?"),
]

HELDOUT = [  # paraphrased / harder questions written after the pipeline was tuned on QA (not used for tuning)
    ("H01", "What is the purpose of the key fob handler component?", ["key fob"]),
    ("H02", "Tell me the threshold speed at which the doors lock themselves.", ["15"]),
    ("H03", "Which software component is responsible for storing data in non-volatile memory?", ["SWC_NvmManager"]),
    ("H04", "How many software components are in the architecture?", ["seven"]),
    ("H05", "Does the lighting component need the speed signal?", ["VehicleSpeed"]),
    ("H06", "For how long is the last speed value kept when its checksum is wrong?", ["100 ms"]),
    ("H07", "Which ECU sends the wheel speed message?", ["ESC"]),
    ("H08", "How are unsupported diagnostic identifiers handled?", ["0x31"]),
    ("H09", "Which runnable executes every 50 ms?", ["LightingCtrl_Run50ms"]),
    ("H10", "Which window function is triggered by holding the key fob for more than two seconds?", ["comfort-close"]),
    ("H11", "What are the states of the central locking state machine?", ["LOCKED", "UNLOCKED", "SUPERLOCKED"]),
    ("H12", "Which interface does the PP_DiagData port use?", ["If_DiagData"]),
    ("H13", "Which component stores the lock state after it changes?", ["SWC_NvmManager"]),
    ("H14", "In which byte order are the CAN signals transmitted?", ["Motorola"]),
    ("H15", "Which CAN message carries the lamp command and how often is it sent?", ["BDC_Lamp", "50"]),
]
HELDOUT_OOS = [
    ("H16", "What is the maximum payload of a CAN FD frame?"),
    ("H17", "Which company manufactures the BDC hardware?"),
    ("H18", "What is the over-the-air update procedure for the BDC?"),
]


def draw_figure(m, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    names = [c[0] for c in m["comps"]]
    cols = 4
    pos = {n: (i % cols * 2.6, -(i // cols) * 1.8) for i, n in enumerate(names)}
    fig, ax = plt.subplots(figsize=(10, 3.6 if len(names) <= 8 else 4))
    for n, (x, y) in pos.items():
        ax.add_patch(FancyBboxPatch((x, y), 2.2, 0.9, boxstyle="round,pad=0.03", fc="#e8eef7", ec="#33507a"))
        ax.text(x + 1.1, y + 0.45, n.replace("SWC_", "SWC_\n"), ha="center", va="center", fontsize=8)
    seen = set()
    for a, b, _ in m["conns"]:
        ca, cb = a.split(".")[0], b.split(".")[0]
        if (ca, cb) in seen or ca == cb:
            continue
        seen.add((ca, cb))
        (x1, y1), (x2, y2) = pos[ca], pos[cb]
        ax.annotate("", xy=(x2 + 1.1, y2 + 0.45), xytext=(x1 + 1.1, y1 + 0.45),
                    arrowprops=dict(arrowstyle="->", color="#555", shrinkA=26, shrinkB=26, lw=0.9))
    ax.set_xlim(-0.3, cols * 2.6)
    ax.set_ylim(-(len(names) - 1) // cols * 1.8 - 0.4, 1.3)
    ax.axis("off")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def render_pdf(m, path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    ver = m["version"]
    H1 = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=16, spaceBefore=14, spaceAfter=6, leading=19)
    H2 = ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=13, spaceBefore=10, spaceAfter=4, leading=16)
    H3 = ParagraphStyle("H3", fontName="Helvetica-Bold", fontSize=11.5, spaceBefore=8, spaceAfter=3, leading=14)
    BODY = ParagraphStyle("B", fontName="Helvetica", fontSize=10, leading=14, spaceAfter=5)
    CAP = ParagraphStyle("C", fontName="Helvetica-Oblique", fontSize=9, leading=11, spaceBefore=4, spaceAfter=3)
    TITLE = ParagraphStyle("T", fontName="Helvetica-Bold", fontSize=24, leading=30, spaceAfter=10)
    SUB = ParagraphStyle("S", fontName="Helvetica", fontSize=14, leading=18, spaceAfter=24)
    CELL = ParagraphStyle("Cell", fontName="Helvetica", fontSize=8, leading=10)
    CELLH = ParagraphStyle("CellH", fontName="Helvetica-Bold", fontSize=8, leading=10)

    def table(hdr, rows, widths):
        data = [[Paragraph(h, CELLH) for h in hdr]] + [[Paragraph(str(c), CELL) for c in r] for r in rows]
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#444444")),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9d9d9")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return t

    def footer(c, d):
        c.saveState()
        c.setFont("Helvetica", 8)
        c.drawString(50, 30, f"BDC-HLD-001 | Version {ver} | Synthetic academic dataset - not a real OEM document")
        c.drawRightString(545, 30, f"Page {d.page}")
        c.restoreState()

    n = len(m["comps"])
    words = {7: "seven", 8: "eight"}
    S = []
    S += [Spacer(1, 120), Paragraph("Body Domain Controller (BDC)", TITLE), Paragraph("High-Level Design Document", SUB),
          table(["Field", "Value"], [("Document ID", "BDC-HLD-001"), ("Document Title", "Body Domain Controller High-Level Design"),
                                     ("Version", ver), ("Date", m["revisions"][-1][1]),
                                     ("Status", "Approved (synthetic dataset)")], [120, 375]), PageBreak()]
    S += [Paragraph("1 Introduction", H1), Paragraph("1.1 Purpose and Scope", H2),
          Paragraph("This document describes the High-Level Design (HLD) of the Body Domain Controller (BDC) application software. "
                    "The BDC is a fictitious ECU created as a synthetic dataset for academic evaluation of document analysis tools. "
                    "The software is based on AUTOSAR Classic Platform release R22-11. "
                    "It implements central locking, power windows and exterior lighting" + (" and mirror folding." if m["v11"] else "."), BODY),
          Paragraph("1.2 Reference Documents", H2),
          Paragraph("The AUTOSAR Classic Platform software component template and RTE specification are used for terminology only. "
                    "No standards text is reproduced in this synthetic document.", BODY),
          Paragraph("1.3 Glossary", H2), Paragraph("Table 1-1: Glossary", CAP),
          table(["Term", "Meaning"], [("SWC", "Software Component"), ("RTE", "Runtime Environment"), ("BSW", "Basic Software"),
                                      ("NVM", "Non-Volatile Memory"), ("DID", "Data Identifier"), ("NRC", "Negative Response Code"),
                                      ("P-Port", "Provided port of a software component"), ("R-Port", "Required port of a software component")],
                [90, 405])]
    S += [Paragraph("2 System Overview", H1), Paragraph("2.1 System Context", H2),
          Paragraph("The BDC receives remote commands from the key fob receiver and the vehicle speed from the ESC ECU. "
                    "It controls the door locks, the power windows and the exterior lamps.", BODY),
          Paragraph("2.2 Platform", H2),
          Paragraph("The BDC communicates on a single high-speed CAN network with a bit rate of 500 kbit/s. "
                    "The application software runs on a synthetic 32-bit microcontroller under an AUTOSAR Classic Platform operating system. "
                    "Application components communicate only through the Runtime Environment (RTE).", BODY)]
    S += [Paragraph("3 Software Architecture", H1), Paragraph("3.1 Architecture Overview", H2),
          Paragraph(f"The application layer of the BDC consists of {words.get(n, n)} software components (SWC) that communicate through the RTE. "
                    "Figure 3-1 shows the components and their relationships. The formal port and connection definitions are given in Sections 4 and 6.", BODY),
          Image(str(ROOT / "Code" / "scripts" / "_fig_tmp.png"), width=440, height=440 * (3.6 / 10)),
          Paragraph("Figure 3-1: BDC software component overview", CAP),
          Paragraph("3.2 Component Catalogue", H2), Paragraph("Table 3-1: Component catalogue", CAP),
          table(["Component", "Type", "Responsibility"], [(a, b, c) for a, b, c, _ in m["comps"]], [120, 80, 295]),
          Paragraph("3.3 Component Descriptions", H2)]
    for i, (name, _, _, desc) in enumerate(m["comps"], 1):
        S += [Paragraph(f"3.3.{i} {name}", H3), Paragraph(" ".join(desc), BODY)]
    S += [Paragraph("4 Port and Interface Specification", H1), Paragraph("4.1 Interface Definitions", H2),
          Paragraph("Table 4-1: Interface definitions", CAP),
          table(["Interface", "Kind", "Data Element / Operation", "Data Type"], m["interfaces"], [90, 95, 160, 150]),
          Paragraph("4.2 Port Specification", H2), Paragraph("Table 4-2: Port specification", CAP),
          table(["Component", "Port", "Direction", "Interface"], m["ports"], [130, 100, 80, 185]),
          Paragraph("4.3 Diagnostic Data Identifiers", H2), Paragraph("Table 4-3: Diagnostic data identifiers", CAP),
          table(["DID", "Name", "Owner Component", "Length (bytes)"], m["dids"], [70, 170, 170, 85])]
    S += [Paragraph("5 Signal Specification", H1), Paragraph("5.1 CAN Signals", H2),
          Paragraph("All signals are transmitted in Motorola byte order. The cycle time Event denotes event-triggered transmission.", BODY),
          Paragraph("Table 5-1: CAN signal specification", CAP),
          table(["Signal", "CAN Message", "CAN ID", "Length (bit)", "Dir", "Cycle (ms)", "Mapped Port"], m["signals"],
                [75, 70, 45, 45, 30, 45, 185])]
    S += [Paragraph("6 Dependencies and Connections", H1), Paragraph("6.1 Connection Table", H2),
          Paragraph("Every required port (R-Port) must be connected to exactly one provided port (P-Port) with a matching interface.", BODY),
          Paragraph("Table 6-1: Connection table", CAP),
          table(["Provider Port", "Requirer Port", "Purpose"], m["conns"], [175, 175, 145])]
    S += [Paragraph("7 Functional Flows", H1)]
    for i, (title, steps) in enumerate(m["flows"].items(), 1):
        S += [Paragraph(f"7.{i} {title}", H2)]
        S += [Paragraph(f"Step {k}: {s}", BODY) for k, s in enumerate(steps, 1)]
    S += [Paragraph("8 Non-Functional Requirements", H1), Paragraph("8.1 Timing and Performance", H2),
          Paragraph("Table 8-1: Non-functional requirements", CAP),
          table(["ID", "Requirement", "Value"], m["nfr"], [55, 330, 110]),
          Paragraph("9 Revision History", H1), Paragraph("Table 9-1: Revision history", CAP),
          table(["Version", "Date", "Change"], m["revisions"], [60, 80, 355])]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=55,
                      title=f"BDC-HLD-001 v{ver}", author="Synthetic dataset").build(S, onFirstPage=footer, onLaterPages=footer)


def main():
    GT.mkdir(parents=True, exist_ok=True)
    kbs = {}
    for ver in ("1.0", "1.1"):
        m = build_model(ver)
        draw_figure(m, ROOT / "Code" / "scripts" / "_fig_tmp.png")
        render_pdf(m, OUT / f"BDC_HLD_v{ver}.pdf")
        kbs[ver] = to_kb(m)
        (GT / f"truth_kb_v{ver}.json").write_text(json.dumps(kbs[ver], indent=1), encoding="utf-8")
        (GT / f"seeded_defects_v{ver}.json").write_text(json.dumps(seeded_defects(m), indent=1), encoding="utf-8")
    (ROOT / "Code" / "scripts" / "_fig_tmp.png").unlink()
    changes = [c["key"] for c in compare_kbs(kbs["1.0"], kbs["1.1"])]
    (GT / "expected_changes_v1.0_to_v1.1.json").write_text(json.dumps(changes, indent=1), encoding="utf-8")
    qa = [dict(id=i, question=q, must_contain=mc, evidence=ev, type=t, answerable=True) for i, q, mc, ev, t in QA]
    qa += [dict(id=i, question=q, must_contain=[], evidence=[], type="out_of_scope", answerable=False) for i, q in OOS]
    (GT / "qa_set.json").write_text(json.dumps(qa, indent=1), encoding="utf-8")
    ho = [dict(id=i, question=q, must_contain=mc, evidence=[], type="heldout", answerable=True) for i, q, mc in HELDOUT]
    ho += [dict(id=i, question=q, must_contain=[], evidence=[], type="out_of_scope", answerable=False) for i, q in HELDOUT_OOS]
    (GT / "qa_heldout.json").write_text(json.dumps(ho, indent=1), encoding="utf-8")
    print("generated", len(qa), "questions;", len(changes), "expected revision changes")


if __name__ == "__main__":
    main()
