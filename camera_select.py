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


def beach_mode(default="loose"):
    """`--beach-mode loose` (default) counts a ball touching the wall even while someone
    holds it or stands next to it, at the cost of some pops from carrying the ball along
    the wall. `--beach-mode strict` (or BALLOON_BEACH_MODE=strict) ignores a ball joined
    to a person."""
    return str(_option("--beach-mode", "BALLOON_BEACH_MODE", default)).lower()


def theme(default="normal"):
    """`--theme halloween` (or BALLOON_THEME=halloween) adds coins, ghosts, bats and
    spiders (halloween.py) and leaves out the game's own background music."""
    return str(_option("--theme", "BALLOON_THEME", default)).lower()


def ball_type(default="color"):
    """`--ball beach` (or BALLOON_BALL=beach) uses the beach-ball impact detector
    (beach_ball.py) instead of the blue/yellow colour trackers."""
    return str(_option("--ball", "BALLOON_BALL", default)).lower()
