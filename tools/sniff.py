"""Capture + decode raw input reports from the AKP03 vendor interface.

Opens VID 0x0300 / PID 0x3002 interface 0 (usage_page 0xffa0) and records every
input report that differs from the previous one, decoding it with the protocol
spec (4ndv/mirajazz + 4ndv/opendeck-akp03) so we can verify against real hardware.

Input report = 512 bytes, header ASCII "ACK", data[9]=code, data[10]=state.

Runs for DURATION seconds (argv[1], default 60) then prints a summary.
"""
import sys
import time
import hid

VID = 0x0300
PID = 0x3002
VENDOR_USAGE_PAGE = 0xFFA0

# code (data[9]) -> human label, per opendeck-akp03/src/inputs.rs
CODE = {
    0x00: "ALL-RELEASED",
    0x01: "LCD key 1", 0x02: "LCD key 2", 0x03: "LCD key 3",
    0x04: "LCD key 4", 0x05: "LCD key 5", 0x06: "LCD key 6",
    0x25: "button 7", 0x30: "button 8", 0x31: "button 9",
    0x90: "enc0 turn -", 0x91: "enc0 turn +",
    0x50: "enc1 turn -", 0x51: "enc1 turn +",
    0x60: "enc2 turn -", 0x61: "enc2 turn +",
    0x33: "enc0 push", 0x35: "enc1 push", 0x34: "enc2 push",
}


def find_vendor_path():
    for d in hid.enumerate(VID, PID):
        if d.get("usage_page") == VENDOR_USAGE_PAGE or d.get("interface_number") == 0:
            return d["path"]
    return None


def decode(data):
    if len(data) < 11:
        return "(short report)"
    hdr = bytes(data[0:3])
    code = data[9]
    state = data[10]
    label = CODE.get(code, f"UNKNOWN(0x{code:02x})")
    st = "press" if state else "release"
    hdr_s = hdr.decode("ascii", "replace")
    return f"hdr={hdr_s!r} code=0x{code:02x} state=0x{state:02x} -> {label} [{st}]"


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    path = find_vendor_path()
    if not path:
        print("Could not find vendor interface (0xffa0 / interface 0).", flush=True)
        return

    dev = hid.device()
    dev.open_path(path)
    dev.set_nonblocking(True)
    print(f"Opened vendor interface. Listening for {duration:.0f}s.", flush=True)
    print(">>> Press all 6 LCD keys, the 3 round buttons, push each of the 3 "
          "knobs, and turn each knob both ways. <<<", flush=True)

    events = []
    last = None
    start = time.time()
    while time.time() - start < duration:
        data = dev.read(512)
        if data:
            tup = tuple(data[:16])
            if tup != last:
                t = time.time() - start
                events.append((t, list(data)))
                last = tup
                # live line so we can peek at the file mid-capture
                hexs = " ".join(f"{b:02x}" for b in data[:14])
                print(f"  t={t:6.2f}s  [{hexs}]  {decode(data)}", flush=True)
        else:
            time.sleep(0.004)

    dev.close()
    print(f"\n===== Captured {len(events)} distinct reports =====", flush=True)


if __name__ == "__main__":
    main()
