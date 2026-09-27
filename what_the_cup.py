
import json
import math
import random
import sys
from pathlib import Path
import turtle

WIDTH, HEIGHT = 920, 650
FPS_MS = 16
SAVE_FILE = Path(__file__).resolve().parent / "what_the_cup_scores.json"
BG = "#101c32"
WHITE = "#f0f5ff"
MUTED = "#a7b8d7"
GOLD = "#ffcd55"
CUP_COLORS = ("#e95f69", "#508de4", "#9b70de", "#31aa94", "#ee9850", "#dc70aa")


def difficulty(level):

    count = min(6, 3 + (level - 1) // 2)
    swaps = 4 + level * 2
    duration = max(12, 43 - (level - 1) * 3)  # frames per swap
    reveal_frames = max(85, 155 - (level - 1) * 5)
    return count, swaps, duration, reveal_frames


def load_best():
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        value = int(data.get("high_score", 0))
        return max(0, value)
    except (OSError, ValueError, TypeError):
        return 0


def save_best(best):
    try:
        SAVE_FILE.write_text(
            json.dumps({"high_score": best}, indent=2), encoding="utf-8"
        )
    except OSError:
        pass  # The game is still playable if this folder is read-only.


def play_sound(kind, screen):

    if sys.platform == "win32":
        try:
            import winsound
            notes = {
                "reveal": ((600, 65),),
                "swap": ((430, 18),),
                "correct": ((750, 85), (1040, 115)),
                "wrong": ((330, 160), (220, 180)),
            }.get(kind, ())
            for hz, ms in notes:
                winsound.Beep(hz, ms)
            return
        except (ImportError, RuntimeError, OSError):
            pass
    try:
        screen.getcanvas().bell()
    except Exception:
        pass  # Some systems have no audible bell.


def make_writer(color=WHITE):
    p = turtle.Turtle(visible=False)
    p.speed(0)
    p.penup()
    p.color(color)
    return p


def register_cup_shape(screen):
    """Draw each cup as a reusable, entirely vector-based compound shape."""
    shape = turtle.Shape("compound")
    body = [(-31, 30), (31, 30), (42, -29), (-42, -29)]
    shape.addcomponent(body, CUP_COLORS[0], "#ffdee5")
    shape.addcomponent([(-31, 30), (31, 30), (28, 22), (-28, 22)], "#ffc6cc", "#ffc6cc")
    shape.addcomponent([(-37, -17), (37, -17), (39, -23), (-39, -23)], "#ae3547", "#ae3547")
    screen.register_shape("cup_shape", shape)


class Cup:
    def __init__(self, identity, slot_x):
        self.identity = identity
        self.slot = identity
        self.x = slot_x
        self.y = 0
        self.sprite = turtle.Turtle(visible=False)
        self.sprite.penup()
        self.sprite.speed(0)
        self.sprite.shape("cup_shape")
        self.sprite.showturtle()
        self.render()

    def render(self):
        self.sprite.goto(self.x, self.y)

    def destroy(self):
        self.sprite.hideturtle()


class WhatTheCup:
    def __init__(self):
        self.screen = turtle.Screen()
        self.screen.setup(WIDTH, HEIGHT)
        self.screen.title("WHAT THE CUP! | by @loqz")
        self.screen.bgcolor(BG)
        self.screen.tracer(0)
        register_cup_shape(self.screen)

        self.decor = make_writer()
        self.header = make_writer()
        self.caption = make_writer(MUTED)
        self.footer = make_writer(MUTED)
        self.slot_labels = make_writer(MUTED)
        self.ball = turtle.Turtle(visible=False)
        self.ball.shape("circle")
        self.ball.shapesize(0.78)
        self.ball.color(GOLD)
        self.ball.penup()
        self.ball.speed(0)
        self.cups = []

        self.best = load_best()
        self.score = 0
        self.level = 1
        self.state = "menu"  # menu -> reveal -> shuffle -> select -> result / over
        self.correct_id = 0
        self.slots = []
        self.frame = 0
        self.swap_index = 0
        self.swap_pair = None
        self.swap_progress = 0
        self.current_swaps = 0
        self.swap_duration = 0
        self.reveal_length = 0
        self.result_frames = 0
        self.correct_guess = False

        self.draw_background()
        self.screen.onclick(self.click)
        self.screen.listen()
        self.screen.onkeypress(self.enter, "Return")
        self.screen.onkeypress(self.restart, "r")
        self.screen.onkeypress(self.restart, "R")
        self.screen.onkeypress(self.screen.bye, "Escape")
        for key in range(1, 7):
            self.screen.onkeypress(lambda n=key: self.choose_slot(n - 1), str(key))

        self.show_menu()
        self.screen.ontimer(self.tick, FPS_MS)
        self.screen.mainloop()

    def draw_background(self):
        d = self.decor
        d.color("#213959")
        d.pensize(3)
        for yy in (-123, -129):
            d.goto(-410, yy)
            d.pendown()
            d.goto(410, yy)
            d.penup()
        d.color("#1b3151")
        for xx in (-425, 425):
            d.goto(xx, -290)
            d.pendown()
            d.goto(xx, 265)
            d.penup()
        d.color(GOLD)
        d.goto(0, 257)
        d.write("WHAT THE CUP!", align="center", font=("Arial", 30, "bold"))
        d.color(MUTED)
        d.goto(0, 228)
        d.write("Watch  •  Remember  •  Choose", align="center", font=("Arial", 12, "normal"))
        self.footer.clear()
        self.footer.goto(0, -293)
        self.footer.write(
            "ENTER = start / next     •     R = restart     •     ESC = quit",
            align="center", font=("Arial", 11, "normal")
        )

    def set_text(self, headline, sub=""):
        self.header.clear()
        self.header.goto(0, 177)
        self.header.write(headline, align="center", font=("Arial", 18, "bold"))
        self.caption.clear()
        self.caption.goto(0, -208)
        self.caption.write(sub, align="center", font=("Arial", 13, "normal"))

    def hud(self):
        self.decor.clear()
        self.draw_background()
        h = self.header
        h.clear()
        h.goto(-392, 174)
        h.write(f"LEVEL {self.level}", font=("Arial", 16, "bold"))
        h.goto(-85, 174)
        h.write(f"SCORE {self.score}", font=("Arial", 16, "bold"))
        h.goto(205, 174)
        h.write(f"BEST {self.best}", font=("Arial", 16, "bold"))

    def show_menu(self):
        self.state = "menu"
        self.hud()
        self.caption.clear()
        self.caption.goto(0, 40)
        self.caption.write("Follow the golden ball as the cups shuffle!", align="center", font=("Arial", 19, "bold"))
        self.caption.goto(0, -5)
        self.caption.write("Click the cup that hides it. One wrong guess ends the run.", align="center", font=("Arial", 14, "normal"))
        self.caption.goto(0, -67)
        self.caption.write("Press ENTER to play", align="center", font=("Arial", 19, "bold"))
        self.caption.goto(0, -218)
        self.caption.write("Mouse: click a cup  •  Keyboard: numbers 1–6", align="center", font=("Arial", 12, "normal"))

    def clear_cups(self):
        for cup in self.cups:
            cup.destroy()
        self.cups.clear()
        self.ball.hideturtle()
        self.slot_labels.clear()

    def start_level(self):
        self.clear_cups()
        self.hud()
        count, self.current_swaps, self.swap_duration, self.reveal_length = difficulty(self.level)
        spacing = min(150, 720 / max(1, count - 1))
        self.slots = [(i - (count - 1) / 2) * spacing for i in range(count)]
        self.cups = [Cup(i, self.slots[i]) for i in range(count)]
        self.slot_labels.clear()
        for i, x in enumerate(self.slots):
            self.slot_labels.goto(x, -94)
            self.slot_labels.write(str(i + 1), align="center", font=("Arial", 14, "bold"))
        self.correct_id = random.randrange(count)
        self.frame = 0
        self.swap_index = 0
        self.swap_pair = None
        self.state = "reveal"
        self.caption.clear()
        self.caption.goto(0, -208)
        self.caption.write("MEMORIZE! The ball is under the lifted cup.", align="center", font=("Arial", 15, "bold"))
        chosen = self.cups[self.correct_id]
        chosen.y = 62
        chosen.render()
        self.ball.goto(self.slots[self.correct_id], -45)
        self.ball.showturtle()
        play_sound("reveal", self.screen)

    def begin_shuffle(self):
        self.state = "shuffle"
        self.ball.hideturtle()
        for cup in self.cups:
            cup.y = 0
            cup.render()
        self.caption.clear()
        self.caption.goto(0, -208)
        self.caption.write("SHUFFLING... Keep your eyes on the ball's cup!", align="center", font=("Arial", 14, "bold"))
        self.swap_index = 0
        self.swap_pair = None

    def next_swap(self):
        if self.swap_index >= self.current_swaps:
            self.state = "select"
            self.caption.clear()
            self.caption.goto(0, -208)
            self.caption.write("YOUR TURN! Click a cup or press its number.", align="center", font=("Arial", 16, "bold"))
            return
        a, b = random.sample(self.cups, 2)
        self.swap_pair = (a, b, a.slot, b.slot)
        self.swap_progress = 0
        if self.swap_index % 3 == 0:
            play_sound("swap", self.screen)

    def animate_shuffle(self):
        if self.swap_pair is None:
            self.next_swap()
            return
        a, b, left_slot, right_slot = self.swap_pair
        self.swap_progress += 1
        t = min(1.0, self.swap_progress / self.swap_duration)
        eased = t * t * (3 - 2 * t)  # smoothstep
        a.x = self.slots[left_slot] * (1 - eased) + self.slots[right_slot] * eased
        b.x = self.slots[right_slot] * (1 - eased) + self.slots[left_slot] * eased
        arc = math.sin(math.pi * t) * 43
        a.y = arc
        b.y = -arc
        a.render()
        b.render()
        if t >= 1:
            a.slot, b.slot = right_slot, left_slot
            a.x, b.x = self.slots[a.slot], self.slots[b.slot]
            a.y = b.y = 0
            a.render()
            b.render()
            self.swap_pair = None
            self.swap_index += 1

    def click(self, x, y):
        if self.state != "select":
            return
        # Hitbox follows each cup's actual landing position.
        for cup in self.cups:
            if abs(x - cup.x) <= 43 and -35 <= y <= 35:
                self.choose_slot(cup.slot)
                return

    def choose_slot(self, slot):
        if self.state != "select":
            return
        selected = next((cup for cup in self.cups if cup.slot == slot), None)
        if selected is None:
            return
        winner = self.cups[self.correct_id]
        selected.y = 65
        selected.render()
        winner.y = 65
        winner.render()
        self.ball.goto(winner.x, -46)
        self.ball.showturtle()
        self.correct_guess = selected is winner
        self.state = "result" if self.correct_guess else "over"
        if self.correct_guess:
            earned = 100 * self.level
            self.score += earned
            if self.score > self.best:
                self.best = self.score
                save_best(self.best)
            self.hud()
            self.caption.clear()
            self.caption.goto(0, -208)
            self.caption.write(f"CORRECT! +{earned} points  •  Press ENTER for level {self.level + 1}", align="center", font=("Arial", 15, "bold"))
            play_sound("correct", self.screen)
        else:
            self.caption.clear()
            self.caption.goto(0, -200)
            self.caption.write("GAME OVER! The golden ball was under the lifted cup.", align="center", font=("Arial", 15, "bold"))
            self.caption.goto(0, -234)
            self.caption.write(f"Final score: {self.score}  •  Press ENTER or R to try again", align="center", font=("Arial", 13, "normal"))
            play_sound("wrong", self.screen)

    def enter(self):
        if self.state == "menu":
            self.start_level()
        elif self.state == "result":
            self.level += 1
            self.start_level()
        elif self.state == "over":
            self.restart()

    def restart(self):
        self.level = 1
        self.score = 0
        self.clear_cups()
        self.start_level()

    def tick(self):
        try:
            if self.state == "reveal":
                self.frame += 1
                if self.frame >= self.reveal_length:
                    self.begin_shuffle()
            elif self.state == "shuffle":
                self.animate_shuffle()
            self.screen.update()
            self.screen.ontimer(self.tick, FPS_MS)
        except turtle.Terminator:
            return


if __name__ == "__main__":
    WhatTheCup()
