# Balloon Pop Game

An interactive augmented reality game where players use physical balls to pop virtual balloons projected onto a surface. The game uses computer vision to track ball movements and detect collisions with virtual balloons.

## Overview

Balloon Pop Game combines a projector and camera setup to create an engaging physical gaming experience. Players throw or roll colored balls (blue and yellow) at a projection surface to pop virtual balloons (red and green). The game features multiple modes, difficulty levels, and power-ups to enhance gameplay.

This is Sterling Baird's fork of [nachman8/balloon-pop-game](https://github.com/nachman8/balloon-pop-game).

## Features

- **Physical Interaction**: Use real balls to interact with virtual elements
- **Multiple Game Modes**: Standard, Time Attack, Survival, and Cooperative
- **Difficulty Levels**: Easy, Normal, and Hard settings
- **Power-ups**: Special abilities like slow motion, double points, and chain reactions
- **Combo System**: Chain hits together for bonus points
- **Visual Effects**: Explosions, trails, sparkles and other visual feedback
- **Analytics**: Track player statistics and achievements
- **Calibration Wizard**: Easy setup process for different environments

## Prerequisites

- Python 3.6+
- A projector
- A webcam/camera
- Blue and yellow physical balls

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/sgbaird/balloon-pop-game.git
   cd balloon-pop-game
   ```

2. Install required dependencies:
   ```
   pip install opencv-python numpy pygame pyyaml
   ```

3. Run the calibration wizard (recommended for first use):
   ```
   python CalibrationWizard.py
   ```

4. Start the game:
   ```
   python main.py
   ```

> **Status on `main`:** the game does not start as committed. `game.py` loads its sounds from `sound/` and its
> balloon images from `png/`, but the sounds are at the top level and the images were never committed, and `main.py`
> imports `video_recorder`, which was also never committed. Pull request
> [#10](https://github.com/sgbaird/balloon-pop-game/pull/10) adds the missing files and moves the sounds.

## System Requirements

- **Projector**: Any projector with sufficient brightness for your environment
- **Camera**: Any webcam capable of at least 30 FPS at 720p resolution
- **Computer**: 
  - 64-bit Windows, macOS, or Linux
  - 8GB RAM recommended
  - Intel Core i5 or equivalent processor
  - Dedicated GPU recommended but not required
- **Windows-specific defaults**: the game and the calibration wizard open camera 0 through DirectShow, and on Windows
  the game window is placed at x = 2000 px, i.e. on a projector set up as a second display to the right of the
  main one (`SDL_VIDEO_WINDOW_POS` near the top of `game.py`)

## Calibration

Before playing, you'll need to calibrate the system using the Calibration Wizard, which guides you through:

1. **Camera Setup**: Configure the camera to see the projection area
2. **Projector Calibration**: Define the corners of the projection area
3. **Color Calibration**: Sample the colors of your physical balls
4. **Ball Size Calibration**: Measure ball sizes at different points in the projection

To run the calibration:
```
python CalibrationWizard.py
```

## Game Modes

### Standard
Competitive mode where red and green players compete for the highest score over a fixed time period.

### Time Attack
Pop as many balloons as possible before time runs out. The spawn rate increases as time decreases.

### Survival
Balloons get progressively faster and more numerous over time. How long can you last?

### Cooperative
Work together to reach a target score before time runs out.

## Power-ups

The game features several power-ups that appear during gameplay:

- **Slow Motion**: Slows down all balloons
- **Double Points**: Doubles the score for each popped balloon
- **Balloon Magnet**: Attracts balloons to the center of the screen
- **Multi-Ball**: Allows hitting multiple balloons with one throw
- **Giant Ball**: Increases the effective size of your ball
- **Freeze**: Temporarily freezes all balloons
- **Chain Reaction**: Creates a chain reaction of pops when a balloon is hit

## Controls

- Physical balls are the main control method
- **ESC**: Quit game
- **P**: Pause/unpause game
- Mouse can be used to navigate menus and manually pop balloons
- **Q** (Survival mode): end the run and show the results

In the camera window opened by `main.py`:

- **q**: stop ball detection
- **d**: toggle the debug overlay
- **r** / **c**: start or stop recording the raw camera feed (`clean_video.avi`) or the feed with detection overlays
  (`contour_video.avi`)

## Project Structure

- `main.py` - Main entry point that initializes the camera and game
- `game.py` - Core game logic, rendering and game states
- `CalibrationWizard.py` - Calibration tool for camera and projector
- `Kalman_filter.py` - Ball trajectory prediction
- `enhanced_effects.py` - Visual effects system
- `game_analytics.py` - Player statistics and achievements (saved to `game_stats.json`)
- `remove_color_overlap.py` - Optional calibration helper: samples the red balloon's colours and narrows the yellow
  ball's colour range in `calibration.yaml` so red balloons are not detected as yellow balls
- `config-system.py` - Configuration manager for `game_config.yaml`; not used by the game (the hyphen in its name
  also keeps it from being imported)
- `menu_system.py` - UI menu system; not used by the game, which draws its own menus in `game.py`
- `video_recorder.py` - Recording utility imported by `main.py`; not in the repository (see the status note above)
- `AGENTS.md` - Notes for coding agents working on this fork, including the `@codex` setup
- `.github/` - The `@codex` GitHub Actions workflows (see [Development](#development))

## Configuration Files

The game uses YAML files for configuration:

- `calibration.yaml` - Color calibration for ball detection
- `ball_calibration.yaml` - Ball size calibration
- `projector_calibration.yaml` - Projector boundaries
- `game_config.yaml` - Read only by `config-system.py`, which the game does not use

The game also writes `game_stats.json` (player statistics).

## Troubleshooting

### Camera not detected
- Ensure your camera is properly connected
- Try a different USB port
- Run `python CalibrationWizard.py` to test the camera

### Poor ball detection
- Adjust lighting conditions
- Recalibrate the color detection system
- Use balls with more vibrant colors

### Performance issues
- Enable frame skipping with `USE_FRAME_SKIP` and `FRAME_SKIP_COUNT` near the top of `main.py` (the other
  detection settings, such as `USE_BACKGROUND_SUBTRACTION` and `SHOW_DEBUG_INFO`, are there too)
- The camera runs at its default resolution; `main.py` does not set one
- Close other resource-intensive applications

## Development

Branches, issues and pull requests for this fork go to `sgbaird/balloon-pop-game`, not upstream. There are no
automated tests: the game needs a camera, a projector and a display. Check changes with `python -m py_compile *.py`
and by playing.

### `@codex` on GitHub

Anyone with write access to this repository can mention `@codex` in an issue (title or body) or in an issue or pull
request comment to start a Codex session on GitHub Actions (`.github/workflows/codex.yml`).

- **Model and effort:** `@codex+<model>:<effort>`, e.g. `@codex:low`; a bare `@codex` uses the defaults.
- **Issues:** a session that changes files works on a new `codex/issue-<n>-<run>` branch and opens a pull request
  whose description holds the write-up; the reply on the issue is one sentence linking it.
- **Pull requests:** the session pushes to the pull request's branch.
- **Progress:** while it runs, its "working on this" comment shows the plan, the latest message and recent
  commands, so anything a session writes there is public.
- **Parallel runs:** every mention starts at once; sessions check for others on the same thread.

`AGENTS.md` has the details, including how the shared Codex login is kept fresh (`codex-keepalive.yml`) and how to
reseed it.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenCV for computer vision capabilities
- PyGame for game rendering
- All contributors and testers
