# -*- coding: utf-8 -*-
import os
import platform


def notify_user(msg: str, title: str = "Trading Bot"):
    try:
        if platform.system() == "Darwin":
            escaped_msg = msg.replace('"', '\\"')
            escaped_title = title.replace('"', '\\"')
            os.system(f'osascript -e \'display notification "{escaped_msg}" with title "{escaped_title}"\'')
    except:
        pass


def play_sound(sound_name: str = "Glass"):
    try:
        if platform.system() == "Darwin":
            sound_path = f"/System/Library/Sounds/{sound_name}.aiff"
            if os.path.exists(sound_path):
                os.system(f"afplay {sound_path} 2>/dev/null &")
    except:
        pass
