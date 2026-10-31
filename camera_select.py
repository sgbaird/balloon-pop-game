import os
import sys


def _option(flag, env, default):
    """Value of `flag N` / `flag=N` on the command line, else the env variable, else default."""
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(flag + "="):
            return arg.split("=", 1)[1]
    return os.environ.get(env, default)


def camera_index(default=0):
    """Camera index from `--camera N` on the command line, else BALLOON_CAMERA, else default."""
    return int(_option("--camera", "BALLOON_CAMERA", default))


def beach_mode(default="strict"):
    """`--beach-mode loose` (or BALLOON_BEACH_MODE=loose) also counts a ball touching the
    wall while someone holds it or stands next to it, at the cost of some pops from
    carrying the ball along the wall. Default: strict."""
    return str(_option("--beach-mode", "BALLOON_BEACH_MODE", default)).lower()


def ball_type(default="color"):
    """`--ball beach` (or BALLOON_BALL=beach) uses the beach-ball impact detector
    (beach_ball.py) instead of the blue/yellow colour trackers."""
    return str(_option("--ball", "BALLOON_BALL", default)).lower()
