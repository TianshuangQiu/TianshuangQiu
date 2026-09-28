"""Community robot maze for the GitHub profile README.

Visitors open an issue titled ``maze|<direction>``; the workflow calls
``python maze/maze.py move <direction> <user>``, which updates ``state.json``
and redraws the maze section of README.md.
"""

import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "maze" / "state.json"
README = ROOT / "README.md"
REPO = "TianshuangQiu/TianshuangQiu"

CELLS = 6  # maze is CELLS x CELLS rooms -> (2*CELLS+1)^2 tiles
WALL, FLOOR, ROBOT, GOAL, TRAIL = "⬛", "⬜", "🤖", "📦", "🟩"
DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
ARROWS = {"up": "⬆️", "down": "⬇️", "left": "⬅️", "right": "➡️"}
START_MARK, END_MARK = "<!-- MAZE:START -->", "<!-- MAZE:END -->"


def generate(seed):
    """Carve a perfect maze with iterative DFS; returns a list of row strings."""
    rng = random.Random(seed)
    size = 2 * CELLS + 1
    grid = [["#"] * size for _ in range(size)]
    stack, seen = [(0, 0)], {(0, 0)}
    grid[1][1] = "."
    while stack:
        r, c = stack[-1]
        options = [(r + dr, c + dc, dr, dc) for dr, dc in DIRS.values()
                   if 0 <= r + dr < CELLS and 0 <= c + dc < CELLS and (r + dr, c + dc) not in seen]
        if not options:
            stack.pop()
            continue
        nr, nc, dr, dc = rng.choice(options)
        grid[2 * r + 1 + dr][2 * c + 1 + dc] = "."
        grid[2 * nr + 1][2 * nc + 1] = "."
        seen.add((nr, nc))
        stack.append((nr, nc))
    return ["".join(row) for row in grid]


def new_maze(state):
    state["seed"] = random.randrange(1 << 30)
    state["grid"] = generate(state["seed"])
    state["robot"] = [1, 1]
    state["goal"] = [2 * CELLS - 1, 2 * CELLS - 1]
    state["trail"] = [[1, 1]]
    state["moves"] = 0


def is_open(grid, r, c):
    return grid[r][c] != "#"


def slide(state, direction):
    """Drive the robot until it hits a wall, a junction, or the goal.

    Returns the number of tiles travelled (0 means it bonked a wall).
    """
    grid, (r, c) = state["grid"], state["robot"]
    dr, dc = DIRS[direction]
    steps = 0
    while is_open(grid, r + dr, c + dc):
        r, c = r + dr, c + dc
        steps += 1
        if [r, c] not in state["trail"]:
            state["trail"].append([r, c])
        if [r, c] == state["goal"]:
            break
        side_exits = sum(is_open(grid, r + sr, c + sc) for sr, sc in DIRS.values()
                         if (sr, sc) not in ((dr, dc), (-dr, -dc)))
        if side_exits:
            break
    state["robot"] = [r, c]
    return steps


def render(state):
    grid, robot, goal = state["grid"], state["robot"], state["goal"]
    trail = {tuple(t) for t in state["trail"]}
    rows = []
    for r, line in enumerate(grid):
        tiles = []
        for c, ch in enumerate(line):
            if [r, c] == robot:
                tiles.append(ROBOT)
            elif [r, c] == goal:
                tiles.append(GOAL)
            elif ch == "#":
                tiles.append(WALL)
            elif (r, c) in trail:
                tiles.append(TRAIL)
            else:
                tiles.append(FLOOR)
        rows.append("".join(tiles))

    def link(d):
        url = f"https://github.com/{REPO}/issues/new?title=maze%7C{d}&body=Just+click+%22Create%22+to+send+the+robot+{d}!"
        return f'<a href="{url}">{ARROWS[d]}&nbsp;{d.capitalize()}</a>'

    board = "<br>\n".join(rows)
    controls = f"{link('up')}<br>\n{link('left')} &nbsp;·&nbsp; {link('right')}<br>\n{link('down')}"

    recent = state["history"][-5:][::-1]
    recent_md = "\n".join(
        f"| {ARROWS[h['dir']]} {h['dir']} | [@{h['user']}](https://github.com/{h['user']}) | {h['result']} |"
        for h in recent) or "| – | – | – |"
    top = Counter(h["user"] for h in state["history"]).most_common(5)
    top_md = "\n".join(f"| [@{u}](https://github.com/{u}) | {n} |" for u, n in top) or "| – | – |"

    return f"""{START_MARK}
🧩 Help My Robot Reach the Box
---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Everyone shares one robot. Click a direction to open an issue, then click **Create**. A GitHub Action drives 🤖 until it hits a wall or reaches a fork, then updates this page within about a minute.

<p align="center">
{board}
</p>

<p align="center">
{controls}
</p>

<p align="center">Moves this maze: <b>{state["moves"]}</b> &nbsp;·&nbsp; Mazes solved: <b>{state["solved"]}</b></p>

<details>
<summary>📜 Recent moves and top drivers</summary>

| Move | Driver | Result |
| --- | --- | --- |
{recent_md}

| Top drivers | Moves |
| --- | --- |
{top_md}

</details>
{END_MARK}"""


def write_readme(state):
    text = README.read_text()
    section = render(state)
    if START_MARK in text:
        text = re.sub(re.escape(START_MARK) + ".*?" + re.escape(END_MARK),
                      lambda _: section, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + section + "\n"
    README.write_text(text)


def load():
    return json.loads(STATE.read_text())


def save(state):
    STATE.write_text(json.dumps(state, indent=1) + "\n")


def main():
    cmd = sys.argv[1]
    if cmd == "init":
        state = {"solved": 0, "history": []}
        new_maze(state)
    else:
        state = load()
    if cmd == "move":
        direction, user = sys.argv[2].strip().lower(), sys.argv[3]
        if direction not in DIRS:
            print(f"🤔 `{direction[:20]}` isn't a direction. Try up, down, left, or right.")
            return
        steps = slide(state, direction)
        state["moves"] += 1
        if steps == 0:
            result = "bonk 💥"
            message = f"💥 *Bonk!* The robot drove {direction} into a wall. Try another direction on the [profile](https://github.com/{REPO})."
        elif state["robot"] == state["goal"]:
            state["solved"] += 1
            result = "reached the box 🎉"
            message = (f"🎉 You delivered the robot to the 📦 after {state['moves']} moves by the community! "
                       f"That's maze #{state['solved']} solved. A new maze has been generated.")
            new_maze(state)
        else:
            result = f"{steps} tile{'s' * (steps > 1)}"
            message = f"🤖 The robot drove {direction} {result}. See where it ended up on the [profile](https://github.com/{REPO})."
        state["history"] = (state["history"] + [{"user": user, "dir": direction, "result": result}])[-500:]
        print(message)
    save(state)
    write_readme(state)


if __name__ == "__main__":
    main()
