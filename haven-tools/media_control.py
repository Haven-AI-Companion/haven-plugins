import sys
import json
import ctypes
import time

# Win32 Keyboard Event Constants
KEYEVENTF_KEYUP = 0x0002
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

def press_key(vk_code, presses=1):
    for _ in range(presses):
        # Press key
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0.05)
        # Release key
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)

def main():
    try:
        # Read from stdin
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            print("Error: Empty input payload.", file=sys.stderr)
            return

        args = json.loads(raw_input)
        action = args.get("action", "").lower().strip()
        count = args.get("count", 1)
        if not isinstance(count, int) or count < 1:
            count = 1

        actions_map = {
            "play_pause": VK_MEDIA_PLAY_PAUSE,
            "next": VK_MEDIA_NEXT_TRACK,
            "previous": VK_MEDIA_PREV_TRACK,
            "volume_up": VK_VOLUME_UP,
            "volume_down": VK_VOLUME_DOWN,
            "mute": VK_VOLUME_MUTE
        }

        if action not in actions_map:
            print(f"Error: Unknown action '{action}'", file=sys.stderr)
            return

        vk = actions_map[action]
        press_key(vk, presses=count)

        response = {
            "status": "success",
            "message": f"Executed action '{action}' (count: {count}) successfully."
        }
        print(json.dumps(response))

    except Exception as e:
        print(f"Error executing media control: {str(e)}", file=sys.stderr)

if __name__ == "__main__":
    main()
