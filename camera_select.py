import os
import sys


def camera_index(default=0):
    """Camera index from `--camera N` on the command line, else BALLOON_CAMERA, else default."""
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--camera" and i + 1 < len(args):
            return int(args[i + 1])
        if arg.startswith("--camera="):
            return int(arg.split("=", 1)[1])
    return int(os.environ.get("BALLOON_CAMERA", default))
