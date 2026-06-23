"""Enumerate the Ajazz Stream Dock HID interfaces.

Lists every HID interface for VID 0x0300 / PID 0x3002 with the attributes we
need to pick the right one to talk to (vendor interface vs keyboard).
"""
import hid

VID = 0x0300
PID = 0x3002


def main():
    found = [d for d in hid.enumerate() if d["vendor_id"] == VID and d["product_id"] == PID]
    if not found:
        print("No device found for VID 0x0300 / PID 0x3002.")
        print("All HID devices currently visible:")
        for d in hid.enumerate():
            print(f"  {d['vendor_id']:#06x}:{d['product_id']:#06x}  "
                  f"if={d.get('interface_number')}  "
                  f"usage_page={d.get('usage_page'):#06x}  usage={d.get('usage'):#06x}  "
                  f"{d.get('product_string')!r}")
        return

    print(f"Found {len(found)} interface(s) for the Stream Dock:\n")
    for d in found:
        print(f"  interface_number : {d.get('interface_number')}")
        print(f"  usage_page       : {d.get('usage_page'):#06x}")
        print(f"  usage            : {d.get('usage'):#06x}")
        print(f"  serial_number    : {d.get('serial_number')!r}")
        print(f"  manufacturer     : {d.get('manufacturer_string')!r}")
        print(f"  product          : {d.get('product_string')!r}")
        print(f"  release_number   : {d.get('release_number')}")
        print(f"  path             : {d.get('path')!r}")
        print()


if __name__ == "__main__":
    main()
