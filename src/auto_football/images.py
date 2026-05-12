from __future__ import annotations

from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from auto_football.config import Settings
from auto_football.schemas import MatchInfo


FINISHED_STATUS_CODES = {"FT", "AET", "PEN", "CANC", "ABD", "AWD", "WO", "8"}
FINISHED_STATUS_TEXT = ("Finished", "Match Finished", "Full Time", "完场", "已结束")


class MatchImageGenerator:
    def __init__(self, settings: Settings) -> None:
        self.output_dir = Path(settings.image_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.http = httpx.Client(timeout=30.0, follow_redirects=True)
        self.canvas_size = (1242, 1660)
        self.font_candidates = [
            Path(r"C:\Windows\Fonts\msyhbd.ttc"),
            Path(r"C:\Windows\Fonts\msyh.ttc"),
            Path(r"C:\Windows\Fonts\simhei.ttf"),
            Path(r"C:\Windows\Fonts\arial.ttf"),
        ]

    def build_assets(self, match: MatchInfo, verdict: str) -> list[str]:
        cover_path = self.output_dir / f"{match.match_id}_cover.png"
        detail_path = self.output_dir / f"{match.match_id}_prediction.png"

        if self._is_finished(match):
            self._build_post_match_cover(match).save(cover_path)
            self._build_post_match_detail(match).save(detail_path)
        else:
            self._build_pre_match_cover(match, verdict).save(cover_path)
            self._build_pre_match_detail(match, verdict).save(detail_path)
        return [str(cover_path.resolve()), str(detail_path.resolve())]

    def _build_pre_match_cover(self, match: MatchInfo, verdict: str) -> Image.Image:
        image = self._make_background(match.theme_color or "#0C233A", "#07111E")
        draw = ImageDraw.Draw(image)

        self._draw_header(draw, match, title="赛前焦点解析")
        self._draw_logo_pair(image, match, top=360, logo_size=(280, 280))

        draw.text((140, 675), match.home_team, font=self._font(62), fill="white")
        away_width = self._text_width(draw, match.away_team, self._font(62))
        draw.text((1100 - away_width, 675), match.away_team, font=self._font(62), fill="white")
        draw.text((525, 648), "VS", font=self._font(120), fill="#FFD663")

        draw.rounded_rectangle((336, 820, 906, 1010), radius=36, fill=(9, 22, 38, 220), outline=(255, 214, 99, 80), width=2)
        draw.text((420, 855), "核心判断", font=self._font(34), fill="#F7DA8F")
        draw.text((388, 910), verdict, font=self._font(54), fill="white")

        self._draw_pre_match_bottom(draw, match, verdict)
        return image

    def _build_pre_match_detail(self, match: MatchInfo, verdict: str) -> Image.Image:
        image = self._make_background(match.theme_color or "#11263D", "#260913")
        draw = ImageDraw.Draw(image)

        self._draw_header(draw, match, title="赛前信息卡")
        draw.text((82, 260), "方向判断", font=self._font(40), fill="#F5D77D")
        draw.text((82, 320), verdict, font=self._font(72), fill="white")

        self._draw_logo_pair(image, match, top=470, logo_size=(220, 220))
        draw.rounded_rectangle((390, 510, 852, 680), radius=28, fill=(255, 255, 255, 18), outline=(255, 255, 255, 32), width=2)
        draw.text((520, 548), "对阵方向", font=self._font(38), fill="#F8DE93")
        draw.text((458, 602), verdict, font=self._font(46), fill="white")

        left_top_label = "主队排名" if match.home_rank is not None else "比赛状态"
        left_top_value = str(match.home_rank) if match.home_rank is not None else (match.fixture_status_text or "状态待确认")
        right_top_label = "客队排名" if match.away_rank is not None else "比赛时间"
        right_top_value = str(match.away_rank) if match.away_rank is not None else match.match_time.strftime("%m-%d %H:%M")
        left_bottom_label = "主队走势" if match.home_recent_form else "主队名称"
        left_bottom_value = " / ".join(match.home_recent_form) if match.home_recent_form else match.home_team
        right_bottom_label = "客队走势" if match.away_recent_form else "客队名称"
        right_bottom_value = " / ".join(match.away_recent_form) if match.away_recent_form else match.away_team

        self._draw_stat_chip(draw, (82, 820), left_top_label, left_top_value)
        self._draw_stat_chip(draw, (642, 820), right_top_label, right_top_value)
        self._draw_stat_chip(draw, (82, 1040), left_bottom_label, left_bottom_value)
        self._draw_stat_chip(draw, (642, 1040), right_bottom_label, right_bottom_value)

        odds_text = self._format_odds(match.odds)
        draw.rounded_rectangle((82, 1315, 1160, 1515), radius=34, fill=(8, 16, 28, 180))
        draw.text((122, 1368), "赔率摘要", font=self._font(34), fill="#F5D77D")
        draw.text((122, 1422), odds_text, font=self._font(40), fill="white")
        return image

    def _build_post_match_cover(self, match: MatchInfo) -> Image.Image:
        image = self._make_background(match.theme_color or "#14283F", "#0B121B")
        draw = ImageDraw.Draw(image)

        self._draw_header(draw, match, title="赛后战报")
        self._draw_logo_pair(image, match, top=330, logo_size=(250, 250))

        draw.text((150, 610), match.home_team, font=self._font(56), fill="white")
        away_width = self._text_width(draw, match.away_team, self._font(56))
        draw.text((1090 - away_width, 610), match.away_team, font=self._font(56), fill="white")

        score = self._score_text(match)
        score_width = self._text_width(draw, score, self._font(148))
        draw.text(((1242 - score_width) // 2, 700), score, font=self._font(148), fill="#FFD663")

        draw.rounded_rectangle((290, 935, 952, 1060), radius=36, fill=(255, 255, 255, 18), outline=(255, 214, 99, 70), width=2)
        summary = self._result_summary(match)
        summary_width = self._text_width(draw, summary, self._font(52))
        draw.text(((1242 - summary_width) // 2, 965), summary, font=self._font(52), fill="white")

        self._draw_post_match_bottom(draw, match)
        return image

    def _build_post_match_detail(self, match: MatchInfo) -> Image.Image:
        image = self._make_background(match.theme_color or "#11263D", "#1D0F18")
        draw = ImageDraw.Draw(image)

        self._draw_header(draw, match, title="赛果信息卡")
        self._draw_logo_pair(image, match, top=340, logo_size=(220, 220))

        score = self._score_text(match)
        score_width = self._text_width(draw, score, self._font(132))
        draw.text(((1242 - score_width) // 2, 430), score, font=self._font(132), fill="#FFD663")

        self._draw_stat_chip(draw, (82, 760), "比赛状态", match.fixture_status_text or "状态待确认")
        self._draw_stat_chip(draw, (642, 760), "结果判断", self._result_summary(match))
        self._draw_stat_chip(draw, (82, 980), "主队", match.home_team)
        self._draw_stat_chip(draw, (642, 980), "客队", match.away_team)

        injury_text = "；".join((match.injuries or [])[:3]) if match.injuries else "暂无明确伤停信息"
        draw.rounded_rectangle((82, 1250, 1160, 1510), radius=34, fill=(8, 16, 28, 180))
        draw.text((122, 1308), "比赛说明", font=self._font(34), fill="#F5D77D")
        draw.text((122, 1360), f"开赛时间：{match.match_time.strftime('%Y-%m-%d %H:%M')}", font=self._font(34), fill="white")
        draw.text((122, 1412), f"伤停摘要：{injury_text}", font=self._font(30), fill="#DCEBFF")
        return image

    def _draw_header(self, draw: ImageDraw.ImageDraw, match: MatchInfo, title: str) -> None:
        draw.rounded_rectangle((60, 56, 1182, 220), radius=36, fill=(248, 249, 251, 235), outline=(255, 255, 255, 26), width=2)
        draw.text((90, 84), title, font=self._font(64), fill="#162332")
        draw.text((92, 156), match.league, font=self._font(34), fill="#5D6C7D")

        status_text = match.fixture_status_text or "状态待确认"
        time_text = match.match_time.strftime("%Y-%m-%d %H:%M")
        pill_text = f"{status_text} • {time_text}"
        pill_width = max(260, 32 + len(pill_text) * 18)
        x0 = 1182 - pill_width
        draw.rounded_rectangle((x0, 96, 1148, 154), radius=24, fill=(255, 208, 90, 230))
        draw.text((x0 + 18, 108), pill_text, font=self._font(24), fill="#182230")

    def _draw_pre_match_bottom(self, draw: ImageDraw.ImageDraw, match: MatchInfo, verdict: str) -> None:
        draw.rounded_rectangle((60, 1130, 1182, 1535), radius=42, fill=(6, 13, 22, 205), outline=(255, 255, 255, 28), width=2)
        draw.text((102, 1180), "内容摘要", font=self._font(36), fill="#F3D888")
        draw.text((102, 1240), f"方向判断：{verdict}", font=self._font(56), fill="white")
        draw.text((102, 1334), f"比赛状态：{match.fixture_status_text or '状态待确认'}", font=self._font(34), fill="#DCEBFF")
        draw.text((102, 1392), f"开赛时间：{match.match_time.strftime('%Y-%m-%d %H:%M')}", font=self._font(34), fill="#DCEBFF")
        injury_text = "；".join((match.injuries or [])[:3]) if match.injuries else "暂无明确伤停信息"
        draw.text((102, 1450), f"伤停摘要：{injury_text}", font=self._font(28), fill="#DCEBFF")

    def _draw_post_match_bottom(self, draw: ImageDraw.ImageDraw, match: MatchInfo) -> None:
        draw.rounded_rectangle((60, 1145, 1182, 1535), radius=42, fill=(6, 13, 22, 205), outline=(255, 255, 255, 28), width=2)
        draw.text((102, 1195), "赛后摘要", font=self._font(36), fill="#F3D888")
        draw.text((102, 1255), f"最终比分：{self._score_text(match)}", font=self._font(56), fill="white")
        draw.text((102, 1348), f"比赛状态：{match.fixture_status_text or '状态待确认'}", font=self._font(34), fill="#DCEBFF")
        draw.text((102, 1406), f"结果判断：{self._result_summary(match)}", font=self._font(34), fill="#DCEBFF")
        draw.text((102, 1464), f"比赛时间：{match.match_time.strftime('%Y-%m-%d %H:%M')}", font=self._font(28), fill="#DCEBFF")

    def _draw_logo_pair(self, image: Image.Image, match: MatchInfo, *, top: int, logo_size: tuple[int, int]) -> None:
        home_logo = self._load_remote_image(match.home_logo_url, logo_size)
        away_logo = self._load_remote_image(match.away_logo_url, logo_size)
        competition_logo = self._load_remote_image(match.competition_logo_url, (112, 112))
        if competition_logo:
            image.alpha_composite(competition_logo, (1088, 240))
        if home_logo:
            image.alpha_composite(home_logo, (120, top))
        if away_logo:
            image.alpha_composite(away_logo, (1242 - 120 - logo_size[0], top))

    def _draw_stat_chip(self, draw: ImageDraw.ImageDraw, top_left: tuple[int, int], label: str, value: str) -> None:
        x, y = top_left
        draw.rounded_rectangle((x, y, x + 518, y + 172), radius=28, fill=(255, 255, 255, 14), outline=(255, 255, 255, 26), width=2)
        draw.text((x + 34, y + 30), label, font=self._font(30), fill="#9AC1FF")
        draw.text((x + 34, y + 86), value, font=self._font(42), fill="white")

    def _make_background(self, primary: str, secondary: str) -> Image.Image:
        width, height = self.canvas_size
        base = Image.new("RGBA", self.canvas_size)
        start = self._hex_to_rgb(primary)
        end = self._hex_to_rgb(secondary)
        draw = ImageDraw.Draw(base)
        for y in range(height):
            ratio = y / max(height - 1, 1)
            color = tuple(int(start[i] + (end[i] - start[i]) * ratio) for i in range(3)) + (255,)
            draw.line((0, y, width, y), fill=color)

        overlay = Image.new("RGBA", self.canvas_size, (255, 255, 255, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.polygon([(0, 0), (520, 0), (770, 380), (0, 520)], fill=(255, 255, 255, 20))
        odraw.polygon([(820, 0), (1242, 0), (1242, 360), (1020, 260)], fill=(245, 203, 90, 26))
        odraw.ellipse((-120, 990, 460, 1570), fill=(255, 255, 255, 14))
        odraw.ellipse((760, 1030, 1410, 1710), fill=(255, 208, 90, 22))
        return Image.alpha_composite(base, overlay)

    def _load_remote_image(self, url: str | None, size: tuple[int, int]) -> Image.Image | None:
        if not url:
            return None
        try:
            response = self.http.get(url)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGBA")
        except Exception:
            return None
        image.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", size, (255, 255, 255, 0))
        x = (size[0] - image.width) // 2
        y = (size[1] - image.height) // 2
        canvas.alpha_composite(image, (x, y))
        return canvas

    def _font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for font_path in self.font_candidates:
            if font_path.exists():
                return ImageFont.truetype(str(font_path), size=size)
        return ImageFont.load_default()

    @staticmethod
    def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    @staticmethod
    def _hex_to_rgb(value: str) -> tuple[int, int, int]:
        raw = value.lstrip("#")
        if len(raw) != 6:
            return (14, 30, 47)
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def _format_odds(payload: dict | None) -> str:
        if not payload:
            return "暂无明确赔率"
        bookmakers = payload.get("bookmakers") or []
        for bookmaker in bookmakers:
            bets = bookmaker.get("bets") or []
            for bet in bets:
                values = bet.get("values") or []
                if values:
                    parts = [f"{item.get('value')} {item.get('odd')}" for item in values[:3]]
                    return " | ".join(parts)
        if isinstance(payload, dict) and "eu" in payload:
            immediate = (payload.get("eu") or {}).get("immediate") or {}
            parts = []
            if immediate.get("win"):
                parts.append(f"主胜 {immediate['win']}")
            if immediate.get("draw"):
                parts.append(f"平 {immediate['draw']}")
            if immediate.get("fail"):
                parts.append(f"客胜 {immediate['fail']}")
            if parts:
                return " | ".join(parts)
        return "暂无明确赔率"

    @staticmethod
    def _is_finished(match: MatchInfo) -> bool:
        if match.fixture_status in FINISHED_STATUS_CODES:
            return True
        status_text = match.fixture_status_text or ""
        if any(token in status_text for token in FINISHED_STATUS_TEXT):
            return True
        return match.home_score is not None and match.away_score is not None and status_text not in {"Not Started", "状态待确认"}

    @staticmethod
    def _score_text(match: MatchInfo) -> str:
        if match.home_score is None or match.away_score is None:
            return "待开赛"
        return f"{match.home_score} : {match.away_score}"

    @staticmethod
    def _result_summary(match: MatchInfo) -> str:
        if match.home_score is None or match.away_score is None:
            return "主队略占优"
        if match.home_score > match.away_score:
            return f"{match.home_team} 取胜"
        if match.home_score < match.away_score:
            return f"{match.away_team} 取胜"
        return "双方战平"
