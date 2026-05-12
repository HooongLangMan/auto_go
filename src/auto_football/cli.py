from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
import os
import re

import typer

from auto_football.config import get_settings
from auto_football.db import Database
from auto_football.douyin_video import (
    DatabaseDouyinVideoTaskStore,
    DouyinVideoPayloadBuilder,
    DouyinVideoPlanner,
    DouyinVideoService,
    PixelleHttpClient,
)
from auto_football.pipeline import AutoFootballPipeline
from auto_football.adapters import PublisherRegistry, get_wechat_access_token
from auto_football.adapters import WechatPublisher
from auto_football.infra.publishers.base import PublishBundle
from auto_football.infra.publishers.xiaohongshu.publisher import XiaohongshuPlaywrightPublisher
from auto_football.domain.services.auto_draft_selector_service import AutoDraftSelectorService
from auto_football.schemas import DouyinVideoMode

app = typer.Typer(help="Auto football content pipeline.")


def build_douyin_video_service(settings, db):
    return DouyinVideoService(
        planner=DouyinVideoPlanner(),
        payload_builder=DouyinVideoPayloadBuilder(),
        provider=PixelleHttpClient(settings),
        task_store=DatabaseDouyinVideoTaskStore(db),
    )


@app.command("doctor")
def doctor() -> None:
    settings = get_settings()
    required = {
        "API_FOOTBALL_KEY": bool(settings.api_football_key),
        "LLM_API_KEY": bool(settings.llm_api_key),
        "POSTGRES_PASSWORD": bool(settings.postgres_password),
        "WECHAT_OA_API_MCP": bool(get_wechat_access_token),
        "WECHAT_APP_ID": bool(settings.wechat_app_id),
        "WECHAT_APP_SECRET": bool(settings.wechat_app_secret),
    }
    typer.echo("Configuration status:")
    for name, ok in required.items():
        typer.echo(f"- {name}: {'OK' if ok else 'MISSING'}")
    typer.echo(f"- RUN_DRY: {settings.run_dry}")
    typer.echo(f"- PUBLISH_ENABLED: {settings.publish_enabled}")
    typer.echo(f"- WECHAT_PUBLISH_ENABLED: {settings.wechat_publish_enabled}")
    typer.echo(f"- XHS_PUBLISH_ENABLED: {settings.xhs_publish_enabled}")


@app.command("init-db")
def init_db() -> None:
    settings = get_settings()
    db = Database(settings)
    db.init_db()
    typer.echo("Database tables initialized.")


@app.command("run")
def run_pipeline(run_date: str | None = typer.Option(None, "--date")) -> None:
    settings = get_settings()
    pipeline = AutoFootballPipeline(settings)
    effective_date = date.fromisoformat(run_date) if run_date else date.today()
    state = pipeline.run(run_date=effective_date)
    typer.echo(
        f"Run finished. fixtures={len(state['fixtures'])}, "
        f"selected={len(state['selected_match_ids'])}, "
        f"enriched={len(state['match_data'])}, "
        f"contents={len(state['contents'])}"
    )


@app.command("preview")
def preview(
    match_id: int | None = typer.Option(None, "--match-id"),
    limit: int = typer.Option(3, "--limit"),
    open_browser: bool = typer.Option(False, "--open"),
) -> None:
    settings = get_settings()
    db = Database(settings)
    payloads = db.get_preview_payloads(match_id=match_id, limit_matches=limit)
    if not payloads:
        typer.echo("No generated content found. Run the pipeline first.")
        raise typer.Exit(code=1)

    output_dir = Path("generated/previews")
    output_dir.mkdir(parents=True, exist_ok=True)

    created_pages: list[Path] = []
    for index, payload in enumerate(payloads):
        previous_match = payloads[index - 1]["match_id"] if index > 0 else None
        next_match = payloads[index + 1]["match_id"] if index < len(payloads) - 1 else None
        page_path = (output_dir / f"match_{payload['match_id']}.html").resolve()
        page_path.write_text(_render_match_html(payload, previous_match, next_match), encoding="utf-8")
        created_pages.append(page_path)

    index_path = (output_dir / "latest_preview.html").resolve()
    index_path.write_text(_render_index_html(payloads), encoding="utf-8")

    if match_id is not None:
        typer.echo(f"Single match preview written to: {created_pages[0]}")
    else:
        typer.echo(f"Preview index written to: {index_path}")
        typer.echo("Single match pages:")
        for path in created_pages:
            typer.echo(f"- {path}")

    if open_browser:
        os.startfile(str(created_pages[0] if match_id is not None else index_path))


@app.command("xhs-status")
def xhs_status() -> None:
    settings = get_settings()
    publisher = XiaohongshuPlaywrightPublisher(settings)
    payload = publisher.status()
    typer.echo(json_dumps(payload))


@app.command("xhs-login")
def xhs_login(
    timeout: int = typer.Option(180, "--timeout"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    settings = get_settings()
    publisher = XiaohongshuPlaywrightPublisher(settings)
    raise typer.Exit(code=publisher.login(timeout_seconds=timeout, force=force))


@app.command("xhs-browser")
def xhs_browser() -> None:
    settings = get_settings()
    publisher = XiaohongshuPlaywrightPublisher(settings)
    raise typer.Exit(code=publisher.ensure_browser())


@app.command("xhs-publish-match")
def xhs_publish_match(match_id: int = typer.Option(..., "--match-id")) -> None:
    settings = get_settings()
    settings = settings.model_copy(update={"xhs_draft_only": False})
    db = Database(settings)
    bundle = db.get_match_bundle(match_id)
    if bundle is None:
        typer.echo(f"Match {match_id} not found.")
        raise typer.Exit(code=1)
    content = bundle["contents"].get("xiaohongshu")
    if content is None:
        typer.echo(f"Match {match_id} has no xiaohongshu content.")
        raise typer.Exit(code=1)

    publisher = XiaohongshuPlaywrightPublisher(settings)
    result = publisher.create_draft(PublishBundle(match=bundle["match"], content=content))
    db.log_publish(match_id, result)
    typer.echo(json_dumps(result.model_dump()))


@app.command("xhs-auto-draft")
def xhs_auto_draft() -> None:
    settings = get_settings()
    db = Database(settings)
    selector = AutoDraftSelectorService()
    picked = selector.select_from_preview_payloads(
        db.get_preview_payloads(limit_matches=12),
        platform="xiaohongshu",
    )
    if picked is None:
        typer.echo("No eligible xiaohongshu draft candidate found.")
        raise typer.Exit(code=1)
    bundle = db.get_match_bundle(picked["match_id"])
    if bundle is None:
        typer.echo(f"Match {picked['match_id']} not found.")
        raise typer.Exit(code=1)
    content = bundle["contents"].get("xiaohongshu")
    if content is None:
        typer.echo(f"Match {picked['match_id']} has no xiaohongshu content.")
        raise typer.Exit(code=1)
    publisher = XiaohongshuPlaywrightPublisher(settings)
    result = publisher.create_draft(PublishBundle(match=bundle["match"], content=content))
    db.log_publish(picked["match_id"], result)
    typer.echo(f"Selected match_id={picked['match_id']}")
    typer.echo(json_dumps(result.model_dump()))


@app.command("wechat-auto-draft")
def wechat_auto_draft() -> None:
    settings = get_settings()
    db = Database(settings)
    selector = AutoDraftSelectorService()
    picked = selector.select_from_preview_payloads(
        db.get_preview_payloads(limit_matches=12),
        platform="wechat",
    )
    if picked is None:
        typer.echo("No eligible wechat draft candidate found.")
        raise typer.Exit(code=1)
    bundle = db.get_match_bundle(picked["match_id"])
    if bundle is None:
        typer.echo(f"Match {picked['match_id']} not found.")
        raise typer.Exit(code=1)
    content = bundle["contents"].get("wechat")
    if content is None:
        typer.echo(f"Match {picked['match_id']} has no wechat content.")
        raise typer.Exit(code=1)
    publisher = WechatPublisher(settings)
    result = publisher.create_draft(PublishBundle(match=bundle["match"], content=content))
    db.log_publish(picked["match_id"], result)
    typer.echo(f"Selected match_id={picked['match_id']}")
    typer.echo(json_dumps(result.model_dump()))


@app.command("douyin-video-submit")
def douyin_video_submit(
    match_id: int = typer.Option(..., "--match-id"),
    mode: str = typer.Option(..., "--mode"),
) -> None:
    settings = get_settings()
    db = Database(settings)
    db.init_db()
    bundle = db.get_match_bundle(match_id)
    if bundle is None:
        typer.echo(f"Match {match_id} not found.")
        raise typer.Exit(code=1)
    service = build_douyin_video_service(settings, db)
    record = service.submit(bundle["match"], DouyinVideoMode(mode))
    typer.echo(json_dumps(record.model_dump()))


@app.command("douyin-video-sync")
def douyin_video_sync(task_id: str = typer.Option(..., "--task-id")) -> None:
    settings = get_settings()
    db = Database(settings)
    db.init_db()
    service = build_douyin_video_service(settings, db)
    record = service.sync(task_id)
    typer.echo(json_dumps(record.model_dump()))


@app.command("douyin-video-run")
def douyin_video_run(
    match_id: int = typer.Option(..., "--match-id"),
    mode: str = typer.Option(..., "--mode"),
) -> None:
    settings = get_settings()
    db = Database(settings)
    db.init_db()
    bundle = db.get_match_bundle(match_id)
    if bundle is None:
        typer.echo(f"Match {match_id} not found.")
        raise typer.Exit(code=1)
    service = build_douyin_video_service(settings, db)
    submitted = service.submit(bundle["match"], DouyinVideoMode(mode))
    if submitted.provider_task_id is None:
        typer.echo(json_dumps(submitted.model_dump()))
        raise typer.Exit(code=0)
    record = service.sync(submitted.provider_task_id)
    typer.echo(json_dumps(record.model_dump()))


def _render_index_html(payloads: list[dict]) -> str:
    cards = []
    for payload in payloads:
        title = f"{payload.get('home_team') or 'Home'} vs {payload.get('away_team') or 'Away'}"
        score = _score_text(payload)
        cards.append(
            f"""
            <a class="match-link" href="./match_{payload['match_id']}.html">
              <div class="match-top">
                <div>
                  <div class="eyebrow">Match #{payload['match_id']}</div>
                  <h2>{escape(title)}</h2>
                </div>
                <div class="status-pill">{escape(payload.get('fixture_status_text') or '状态待确认')}</div>
              </div>
              <div class="meta">{escape(payload['league'])}</div>
              <div class="meta">{escape(_format_time(payload['match_time']))}</div>
              <div class="score">{escape(score)}</div>
            </a>
            """
        )
    return _page_shell(
        "内容预览目录",
        "按比赛逐场查看内容成品、比赛时间、状态和配图。",
        "".join(cards),
        extra_styles="""
        .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:18px; }
        .match-link { display:block; text-decoration:none; color:inherit; padding:22px; border-radius:24px; background:#fffdfa; border:1px solid #eadfcd; box-shadow:0 14px 34px rgba(22,28,33,.05); }
        .match-link:hover { transform:translateY(-2px); box-shadow:0 18px 40px rgba(22,28,33,.09); }
        .match-top { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
        .match-top h2 { margin:6px 0 0; font-size:26px; line-height:1.25; }
        .status-pill { padding:8px 12px; border-radius:999px; background:#17202b; color:#fff; font-size:13px; white-space:nowrap; }
        .meta { margin-top:10px; color:#5f6670; font-size:14px; }
        .score { margin-top:18px; font-size:28px; font-weight:700; color:#bd4b2b; }
        """,
        body=f'<section class="grid">{"".join(cards)}</section>',
    )


def _render_match_html(payload: dict, previous_match: int | None, next_match: int | None) -> str:
    sections = []
    for content in payload["contents"]:
        image_html = "".join(
            f'<img src="{Path(image).resolve().as_uri()}" alt="{escape(content["title"])}" />'
            for image in content["images"]
            if Path(image).exists()
        )
        sections.append(
            f"""
            <section class="platform-card">
              <div class="platform-tag">{escape(content["platform"])}</div>
              <h3>{escape(content["title"])}</h3>
              <div class="meta-row">
                <span>mode: {escape(content.get("mode") or "unknown")}</span>
                <span>account: {escape(content.get("account_id") or "default")}</span>
                <span>status: {escape(content.get("status") or "drafted")}</span>
                <span>字数：{len(content["content"])}</span>
                <span>生成时间：{escape(_format_time(content["created_at"]))}</span>
              </div>
              <div class="content">{_format_content_html(content["content"])}</div>
              <div class="images">{image_html}</div>
            </section>
            """
        )

    nav = ['<a class="nav-btn" href="./latest_preview.html">返回目录</a>']
    if previous_match is not None:
        nav.append(f'<a class="nav-btn" href="./match_{previous_match}.html">上一场</a>')
    if next_match is not None:
        nav.append(f'<a class="nav-btn" href="./match_{next_match}.html">下一场</a>')

    title = f"{payload.get('home_team') or 'Home'} vs {payload.get('away_team') or 'Away'}"
    summary = f"""
    <section class="match-summary">
      <div class="summary-left">
        <div class="eyebrow">Match #{payload['match_id']}</div>
        <h2>{escape(title)}</h2>
        <div class="meta-stack">
          <div><strong>联赛：</strong>{escape(payload['league'])}</div>
          <div><strong>比赛时间：</strong>{escape(_format_time(payload['match_time']))}</div>
          <div><strong>比赛状态：</strong>{escape(payload.get('fixture_status_text') or '状态待确认')}</div>
          <div><strong>流程状态：</strong>{escape(payload.get('workflow_status') or '未知')}</div>
          <div><strong>ClubElo：</strong>{escape(_elo_text(payload))}</div>
          <div><strong>外部补充条目：</strong>{payload.get('source_documents_count') or 0}</div>
        </div>
      </div>
      <div class="summary-score">
        <div class="score-label">当前比分</div>
        <div class="score-value">{escape(_score_text(payload))}</div>
      </div>
    </section>
    <nav class="nav-row">{''.join(nav)}</nav>
    """
    briefs = payload.get("knowledge_briefs") or []
    if briefs:
        summary += "<section class=\"platform-card\"><div class=\"platform-tag\">knowledge</div><h3>融合补充信息</h3>"
        summary += "".join(f"<p>{escape(item)}</p>" for item in briefs)
        summary += "</section>"
    return _page_shell(
        f"{title} 预览",
        "单场查看模式：减少干扰，方便你逐场审内容、看图和判断状态。",
        "".join(sections),
        extra_styles="""
        .match-summary { display:flex; justify-content:space-between; gap:18px; align-items:flex-start; padding:24px; border:1px solid #e8decc; border-radius:24px; background:#fffdfa; }
        .match-summary h2 { margin:6px 0 0; font-size:34px; line-height:1.2; }
        .meta-stack { margin-top:14px; display:grid; gap:8px; color:#51606d; }
        .summary-score { min-width:220px; padding:18px; border-radius:22px; background:#17202b; color:#fff; text-align:center; }
        .score-label { font-size:13px; letter-spacing:.08em; text-transform:uppercase; opacity:.75; }
        .score-value { margin-top:12px; font-size:44px; font-weight:700; }
        .nav-row { display:flex; gap:12px; flex-wrap:wrap; margin:18px 0 8px; }
        .nav-btn { display:inline-block; padding:10px 14px; border-radius:999px; background:#fffdfa; border:1px solid #e5d8c6; color:#17202b; text-decoration:none; }
        .platform-card { margin-top:18px; padding:22px; border-radius:24px; background:#fffdfa; border:1px solid #eadfcd; box-shadow:0 14px 34px rgba(22,28,33,.05); }
        .platform-tag { display:inline-block; padding:6px 10px; border-radius:999px; background:#17202b; color:#fff; font-size:12px; letter-spacing:.04em; text-transform:uppercase; }
        .platform-card h3 { margin:14px 0 8px; font-size:26px; line-height:1.35; }
        .meta-row { display:flex; gap:14px; flex-wrap:wrap; color:#6b7280; font-size:14px; margin-bottom:14px; }
        .content p { margin:0 0 16px; line-height:1.85; font-size:16px; }
        .content .subhead { margin:14px 0 10px; font-size:17px; font-weight:700; color:#8d2f1f; }
        .images { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; margin-top:18px; }
        .images img { width:100%; border-radius:18px; border:1px solid #e8e0d4; background:#f6f3ec; }
        @media (max-width: 780px) { .match-summary { flex-direction:column; } .summary-score { min-width:auto; width:100%; } }
        """,
        body=f"{summary}{''.join(sections)}",
    )


def _page_shell(title: str, subtitle: str, cards_html: str, *, extra_styles: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f3efe7;
      --ink: #17202b;
      --line: #d9d1c5;
      --accent: #bd4b2b;
    }}
    * {{ box-sizing: border-box; transition: box-shadow .18s ease, transform .18s ease; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(189,75,43,0.10), transparent 24%),
        linear-gradient(180deg, #f9f6ef 0%, var(--bg) 100%);
      color: var(--ink);
    }}
    .page {{ width:min(1100px, calc(100% - 32px)); margin:32px auto 60px; }}
    .hero {{ margin-bottom:22px; padding:28px 30px; border:1px solid var(--line); border-radius:30px; background:rgba(255,253,250,0.88); backdrop-filter: blur(10px); }}
    .hero h1 {{ margin:0 0 8px; font-size:36px; }}
    .hero p {{ margin:0; color:#4a5462; }}
    .eyebrow {{ color:var(--accent); font-size:13px; letter-spacing:.08em; text-transform:uppercase; }}
    {extra_styles}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <h1>{escape(title)}</h1>
      <p>{escape(subtitle)}</p>
    </section>
    {body}
  </main>
</body>
</html>
"""


def _format_content_html(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("**", "")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        return "<p>暂无内容</p>"
    blocks = []
    for block in [item.strip() for item in normalized.split("\n\n") if item.strip()]:
        block = re.sub(r"^[#>\-\*\d\.\s]+", "", block).strip()
        if not block:
            continue
        block_html = escape(block).replace("\n", "<br>")
        if len(block) <= 18 and not any(p in block for p in "，。！？："):
            blocks.append(f'<div class="subhead">{block_html}</div>')
        else:
            blocks.append(f"<p>{block_html}</p>")
    return "".join(blocks)


def _format_time(value) -> str:
    if value is None:
        return "时间待确认"
    return str(value).replace("T", " ").replace("+00:00", " UTC")


def _score_text(payload: dict) -> str:
    home = payload.get("home_score")
    away = payload.get("away_score")
    if home is None or away is None:
        return "待开赛 / 无比分"
    return f"{home} : {away}"


def _elo_text(payload: dict) -> str:
    home_elo = payload.get("home_elo")
    away_elo = payload.get("away_elo")
    if home_elo is None or away_elo is None:
        return "暂无"
    return f"{payload.get('home_team') or '主队'} {home_elo:.1f} / {payload.get('away_team') or '客队'} {away_elo:.1f}"


def json_dumps(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    app()
