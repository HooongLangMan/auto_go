from __future__ import annotations

from auto_football.config import Settings
from auto_football.db import Database
from auto_football.schemas import DouyinVideoMode, DouyinVideoTaskRecord, DouyinVideoTaskStatus


def test_database_saves_and_updates_douyin_video_tasks(tmp_path) -> None:
    db_path = tmp_path / "douyin_video.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()

    saved = db.save_douyin_video_task(
        DouyinVideoTaskRecord(
            match_id=501,
            video_mode=DouyinVideoMode.PRE_MATCH,
            provider_task_id="task-1",
            status=DouyinVideoTaskStatus.QUEUED,
            payload_snapshot={"match_id": 501},
        )
    )

    assert saved.provider_task_id == "task-1"
    assert db.get_douyin_video_task("task-1").status == DouyinVideoTaskStatus.QUEUED

    updated = db.update_douyin_video_task(
        "task-1",
        status=DouyinVideoTaskStatus.SUCCEEDED,
        video_url="https://video.example/final.mp4",
        error_message=None,
    )

    assert updated.status == DouyinVideoTaskStatus.SUCCEEDED
    assert updated.video_url == "https://video.example/final.mp4"
