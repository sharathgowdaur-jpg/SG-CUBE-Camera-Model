"""
SG CUBE — Live Mouse Control Telemetry Benchmark
Executes real Windows cursor movements, clicks, scrolls, drags, and bounds checks,
recording millisecond-level telemetry and coordinate diffs.
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.mouse_controller import get_mouse_controller

def run_telemetry():
    mouse = get_mouse_controller()
    telemetry = []

    print("=== SG CUBE VOICE MOUSE CONTROL LIVE TELEMETRY ===")
    
    # 1. Initial State
    x0, y0 = mouse.get_position()
    bounds = mouse.get_screen_bounds()
    print(f"[INIT] Cursor Position: ({x0}, {y0}) | Desktop Virtual Bounds: {bounds}")
    telemetry.append({"step": "init", "pos": (x0, y0), "bounds": bounds})

    # 2. Relative Move Right 120px
    res1 = mouse.move("right", 120)
    x1, y1 = mouse.get_position()
    print(f"[MOVE 1] {res1.spoken_response} -> New Pos: ({x1}, {y1}) | Latency: {res1.latency_ms:.3f} ms")
    telemetry.append({"step": "move_right", "latency_ms": res1.latency_ms, "prev": res1.previous_pos, "curr": (x1, y1), "spoken": res1.spoken_response})

    # 3. Relative Move Down 80px
    res2 = mouse.move("down", 80)
    x2, y2 = mouse.get_position()
    print(f"[MOVE 2] {res2.spoken_response} -> New Pos: ({x2}, {y2}) | Latency: {res2.latency_ms:.3f} ms")
    telemetry.append({"step": "move_down", "latency_ms": res2.latency_ms, "prev": res2.previous_pos, "curr": (x2, y2), "spoken": res2.spoken_response})

    # 4. Click
    res3 = mouse.click("left")
    print(f"[CLICK] {res3.spoken_response} | Latency: {res3.latency_ms:.3f} ms")
    telemetry.append({"step": "click_left", "latency_ms": res3.latency_ms, "spoken": res3.spoken_response})

    # 5. Double Click
    res4 = mouse.double_click("left")
    print(f"[DBL_CLICK] {res4.spoken_response} | Latency: {res4.latency_ms:.3f} ms")
    telemetry.append({"step": "double_click", "latency_ms": res4.latency_ms, "spoken": res4.spoken_response})

    # 6. Right Click
    res5 = mouse.right_click()
    print(f"[RIGHT_CLICK] {res5.spoken_response} | Latency: {res5.latency_ms:.3f} ms")
    telemetry.append({"step": "right_click", "latency_ms": res5.latency_ms, "spoken": res5.spoken_response})

    # 7. Scroll Down 4 notches
    res6 = mouse.scroll("down", 4)
    print(f"[SCROLL] {res6.spoken_response} | Latency: {res6.latency_ms:.3f} ms")
    telemetry.append({"step": "scroll_down", "latency_ms": res6.latency_ms, "spoken": res6.spoken_response})

    # 8. Drag Right 60px
    res7 = mouse.drag("right", 60)
    x7, y7 = mouse.get_position()
    print(f"[DRAG] {res7.spoken_response} -> New Pos: ({x7}, {y7}) | Latency: {res7.latency_ms:.3f} ms")
    telemetry.append({"step": "drag_right", "latency_ms": res7.latency_ms, "prev": res7.previous_pos, "curr": (x7, y7), "spoken": res7.spoken_response})

    # 9. Query Position
    res8 = mouse.get_position_spoken()
    print(f"[POSITION] {res8.spoken_response} | Latency: {res8.latency_ms:.3f} ms")
    telemetry.append({"step": "get_position", "latency_ms": res8.latency_ms, "spoken": res8.spoken_response})

    # 10. Out-of-bounds rejection test
    res9 = mouse.move_absolute(99999, 99999)
    print(f"[OOB REJECT] Success: {res9.success} | Spoken: '{res9.spoken_response}' | Latency: {res9.latency_ms:.3f} ms")
    telemetry.append({"step": "oob_reject", "success": res9.success, "spoken": res9.spoken_response, "latency_ms": res9.latency_ms})

    # 11. Move back to original position
    res10 = mouse.move_absolute(x0, y0)
    cur_x, cur_y = mouse.get_position()
    print(f"[RESTORE] Returned to ({cur_x}, {cur_y}) | Latency: {res10.latency_ms:.3f} ms")
    telemetry.append({"step": "restore_position", "latency_ms": res10.latency_ms, "final_pos": (cur_x, cur_y)})

    # Summary
    avg_latency = sum(t["latency_ms"] for t in telemetry if "latency_ms" in t) / len([t for t in telemetry if "latency_ms" in t])
    print(f"\n=== BENCHMARK COMPLETE: Average Latency: {avg_latency:.3f} ms ===")

    out_file = os.path.join(os.path.dirname(__file__), "..", "data", "mouse_telemetry.json")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(telemetry, f, indent=2)
    print(f"Telemetry saved to {out_file}")

if __name__ == "__main__":
    run_telemetry()
