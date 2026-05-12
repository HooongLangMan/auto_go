from __future__ import annotations

import random
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class BehaviorProfile:
    name: str
    typing_delay_min_ms: int
    typing_delay_max_ms: int
    typo_rate: float
    pause_rate: float
    hover_min_ms: int
    hover_max_ms: int
    click_offset_ratio_min: float
    click_offset_ratio_max: float
    invalid_scroll_rate: float
    blank_mouse_roam_rate: float
    false_hover_rate: float
    long_delete_rate: float


BEHAVIOR_PROFILES: dict[str, BehaviorProfile] = {
    "A": BehaviorProfile(
        name="A",
        typing_delay_min_ms=40,
        typing_delay_max_ms=120,
        typo_rate=0.04,
        pause_rate=0.08,
        hover_min_ms=40,
        hover_max_ms=150,
        click_offset_ratio_min=0.38,
        click_offset_ratio_max=0.62,
        invalid_scroll_rate=0.06,
        blank_mouse_roam_rate=0.08,
        false_hover_rate=0.05,
        long_delete_rate=0.03,
    ),
    "B": BehaviorProfile(
        name="B",
        typing_delay_min_ms=80,
        typing_delay_max_ms=250,
        typo_rate=0.01,
        pause_rate=0.16,
        hover_min_ms=120,
        hover_max_ms=300,
        click_offset_ratio_min=0.42,
        click_offset_ratio_max=0.58,
        invalid_scroll_rate=0.05,
        blank_mouse_roam_rate=0.06,
        false_hover_rate=0.03,
        long_delete_rate=0.02,
    ),
    "C": BehaviorProfile(
        name="C",
        typing_delay_min_ms=70,
        typing_delay_max_ms=220,
        typo_rate=0.05,
        pause_rate=0.18,
        hover_min_ms=100,
        hover_max_ms=260,
        click_offset_ratio_min=0.35,
        click_offset_ratio_max=0.65,
        invalid_scroll_rate=0.10,
        blank_mouse_roam_rate=0.10,
        false_hover_rate=0.06,
        long_delete_rate=0.08,
    ),
}


class HumanNoiseEngine:
    def __init__(self, profile: BehaviorProfile) -> None:
        self.profile = profile

    def maybe_noise(self, page, *, anchor_locator=None) -> None:
        roll = random.random()
        if roll < self.profile.blank_mouse_roam_rate:
            self._roam_blank_area(page)
        elif roll < self.profile.blank_mouse_roam_rate + self.profile.invalid_scroll_rate:
            self._micro_scroll(page)
        elif roll < self.profile.blank_mouse_roam_rate + self.profile.invalid_scroll_rate + self.profile.false_hover_rate:
            self._false_hover(page, anchor_locator=anchor_locator)

    def _roam_blank_area(self, page) -> None:
        page.mouse.move(random.randint(30, 180), random.randint(80, 220), steps=random.randint(6, 14))
        time.sleep(random.uniform(0.2, 0.8))

    def _micro_scroll(self, page) -> None:
        page.mouse.wheel(0, random.randint(90, 150))
        time.sleep(random.uniform(0.12, 0.35))
        page.mouse.wheel(0, -random.randint(90, 150))
        time.sleep(random.uniform(0.12, 0.35))

    def _false_hover(self, page, *, anchor_locator=None) -> None:
        if anchor_locator is not None:
            box = anchor_locator.bounding_box()
            if box:
                x = box["x"] + box["width"] * random.uniform(0.1, 0.9)
                y = max(10, box["y"] - random.uniform(8, 24))
                page.mouse.move(x, y, steps=random.randint(4, 10))
                time.sleep(random.uniform(0.15, 0.45))
                page.mouse.move(x + random.uniform(16, 40), y + random.uniform(8, 20), steps=random.randint(3, 8))
                time.sleep(random.uniform(0.1, 0.2))


class PlaywrightHumanizer:
    def __init__(self, profile_name: str | None = None) -> None:
        self.profile = BEHAVIOR_PROFILES.get((profile_name or "").strip().upper()) or random.choice(list(BEHAVIOR_PROFILES.values()))
        self.noise = HumanNoiseEngine(self.profile)

    def pause(self, min_ms: int = 120, max_ms: int = 420) -> None:
        time.sleep(random.uniform(min_ms, max_ms) / 1000)

    def maybe_noise(self, page, *, anchor_locator=None) -> None:
        self.noise.maybe_noise(page, anchor_locator=anchor_locator)

    def stage_transition(self, page, label: str) -> None:
        del label
        self.pause(180, 420)
        self.maybe_noise(page)

    def short_review_pause(self) -> None:
        self.pause(260, 640)

    def click_locator(self, page, locator) -> None:
        box = locator.bounding_box()
        if box:
            x = box["x"] + box["width"] * random.uniform(self.profile.click_offset_ratio_min, self.profile.click_offset_ratio_max)
            y = box["y"] + box["height"] * random.uniform(self.profile.click_offset_ratio_min, self.profile.click_offset_ratio_max)
            page.mouse.move(x, y, steps=random.randint(8, 20))
            self.pause(self.profile.hover_min_ms, self.profile.hover_max_ms)
            if random.random() < self.profile.false_hover_rate:
                self.noise._false_hover(page, anchor_locator=locator)
                page.mouse.move(x, y, steps=random.randint(3, 8))
            page.mouse.down()
            if random.random() < 0.2:
                page.mouse.move(x + random.uniform(-2, 2), y + random.uniform(-2, 2), steps=2)
            self.pause(30, 120)
            page.mouse.up()
            self.pause(120, 320)
            return
        locator.click()
        self.pause(120, 320)

    def type_into(self, page, locator, text: str) -> None:
        self.click_locator(page, locator)
        page.keyboard.press("Control+A")
        self.pause(50, 120)
        page.keyboard.press("Backspace")
        self.pause(80, 160)
        if random.random() < self.profile.long_delete_rate:
            self.pause(220, 480)
        for index, char in enumerate(text):
            if char == "\n":
                page.keyboard.press("Enter")
            else:
                page.keyboard.type(char)
            if random.random() < self.profile.typo_rate and char.strip():
                wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                page.keyboard.type(wrong_char)
                self.pause(40, 110)
                page.keyboard.press("Backspace")
                self.pause(50, 120)
                page.keyboard.type(char)
            if index and index % random.randint(25, 60) == 0:
                self.pause(300, 900)
                if random.random() < self.profile.invalid_scroll_rate:
                    self.noise._micro_scroll(page)
            else:
                self.pause(self.profile.typing_delay_min_ms, self.profile.typing_delay_max_ms)
        if random.random() < self.profile.pause_rate:
            self.pause(240, 720)

    def review_scroll(self, page) -> None:
        for _ in range(random.randint(4, 7)):
            page.mouse.wheel(0, random.randint(300, 700))
            self.pause(180, 480)
        for _ in range(random.randint(4, 7)):
            page.mouse.wheel(0, -random.randint(300, 700))
            self.pause(180, 480)
