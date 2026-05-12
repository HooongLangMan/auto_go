from datetime import datetime, timezone

from auto_football.config import Settings
from auto_football.db import Database
from auto_football.schemas import MergedMatchContext, SourceDocument


def test_database_can_rehydrate_latest_merged_context_snapshot(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'hit_layer.db').as_posix()}")
    db = Database(settings)
    db.init_db()

    db.save_source_documents(
        run_id=None,
        fixture_id=8801,
        documents=[
            SourceDocument(
                source="fbref",
                source_type="team_stat_snapshot",
                team_name="Liverpool",
                title="fbref stat snapshot",
                summary="Liverpool recent xG edge is strong.",
                content_text="Liverpool recent xG edge is strong.",
                crawled_at=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
                payload={"summary": "Liverpool recent xG edge is strong."},
            )
        ],
    )
    db.save_merged_context(
        run_id=None,
        context=MergedMatchContext(
            fixture_id=8801,
            cache_key="fixture-8801",
            api_snapshot={"fixture": {"id": 8801}},
            crawler_documents=[],
            merged_payload={
                "knowledge_briefs": ["[fbref] Liverpool recent xG edge is strong."],
                "coverage": {"total_signals": 4, "ready": True},
            },
        ),
    )

    snapshot = db.get_latest_context_snapshot(8801)

    assert snapshot is not None
    assert snapshot["merged_payload"]["coverage"]["ready"] is True
    assert snapshot["source_documents"][0]["source"] == "fbref"

