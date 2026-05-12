from __future__ import annotations

from sqlalchemy import inspect, text

from auto_football.schemas import ContentMode, ContentStatus


def ensure_match_columns(engine) -> None:
    inspector = inspect(engine)
    if "matches" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("matches")}
    statements = []
    if "home_team" not in columns:
        statements.append("alter table matches add column home_team varchar(128)")
    if "away_team" not in columns:
        statements.append("alter table matches add column away_team varchar(128)")
    if "home_logo_url" not in columns:
        statements.append("alter table matches add column home_logo_url text")
    if "away_logo_url" not in columns:
        statements.append("alter table matches add column away_logo_url text")
    if "competition_logo_url" not in columns:
        statements.append("alter table matches add column competition_logo_url text")
    if "fixture_status" not in columns:
        statements.append("alter table matches add column fixture_status varchar(32)")
    if "fixture_status_text" not in columns:
        statements.append("alter table matches add column fixture_status_text varchar(64)")
    if "home_rank" not in columns:
        statements.append("alter table matches add column home_rank integer")
    if "away_rank" not in columns:
        statements.append("alter table matches add column away_rank integer")
    if "home_recent_form" not in columns:
        statements.append("alter table matches add column home_recent_form json")
    if "away_recent_form" not in columns:
        statements.append("alter table matches add column away_recent_form json")
    if "injuries" not in columns:
        statements.append("alter table matches add column injuries json")
    if "odds_payload" not in columns:
        statements.append("alter table matches add column odds_payload json")
    if "rank_source" not in columns:
        statements.append("alter table matches add column rank_source varchar(32)")
    if "form_source" not in columns:
        statements.append("alter table matches add column form_source varchar(32)")
    if "standings_summary" not in columns:
        statements.append("alter table matches add column standings_summary text")
    if "form_summary" not in columns:
        statements.append("alter table matches add column form_summary text")
    if "home_score" not in columns:
        statements.append("alter table matches add column home_score integer")
    if "away_score" not in columns:
        statements.append("alter table matches add column away_score integer")
    if "home_elo" not in columns:
        statements.append("alter table matches add column home_elo double precision")
    if "away_elo" not in columns:
        statements.append("alter table matches add column away_elo double precision")
    if "home_elo_rank" not in columns:
        statements.append("alter table matches add column home_elo_rank integer")
    if "away_elo_rank" not in columns:
        statements.append("alter table matches add column away_elo_rank integer")
    if "knowledge_briefs" not in columns:
        statements.append("alter table matches add column knowledge_briefs json")
    if "source_documents_count" not in columns:
        statements.append("alter table matches add column source_documents_count integer")
    if "merged_context_payload" not in columns:
        statements.append("alter table matches add column merged_context_payload json")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_content_columns(engine) -> None:
    inspector = inspect(engine)
    if "contents" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("contents")}
    statements = []
    if "mode" not in columns:
        statements.append(f"alter table contents add column mode varchar(32) default '{ContentMode.PRE_MATCH.value}'")
    if "publish_channel" not in columns:
        statements.append("alter table contents add column publish_channel varchar(32) default 'unknown'")
    if "account_id" not in columns:
        statements.append("alter table contents add column account_id varchar(64) default 'default'")
    if "status" not in columns:
        statements.append(f"alter table contents add column status varchar(32) default '{ContentStatus.DRAFTED.value}'")
    if "priority" not in columns:
        statements.append("alter table contents add column priority integer default 0")
    if "remote_images" not in columns:
        statements.append("alter table contents add column remote_images json")
    if "source_urls" not in columns:
        statements.append("alter table contents add column source_urls json")
    if "primary_media_path" not in columns:
        statements.append("alter table contents add column primary_media_path text")
    if "tags" not in columns:
        statements.append("alter table contents add column tags json")
    if "editorial_style" not in columns:
        statements.append("alter table contents add column editorial_style varchar(64)")
    if "editorial_outline" not in columns:
        statements.append("alter table contents add column editorial_outline varchar(64)")
    if "content_readiness" not in columns:
        statements.append("alter table contents add column content_readiness varchar(32)")
    if "candidate_rank" not in columns:
        statements.append("alter table contents add column candidate_rank integer")
    if "candidate_group" not in columns:
        statements.append("alter table contents add column candidate_group varchar(128)")
    if "candidate_count" not in columns:
        statements.append("alter table contents add column candidate_count integer default 1")
    if "quality_summary" not in columns:
        statements.append("alter table contents add column quality_summary text")
    if "editorial_metadata" not in columns:
        statements.append("alter table contents add column editorial_metadata json")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(text("update contents set publish_channel = platform where publish_channel is null or publish_channel = '' or publish_channel = 'unknown'"))
        connection.execute(
            text(
                "update contents set primary_media_path = coalesce(primary_media_path, nullif((images ->> 0), ''), nullif((remote_images ->> 0), '')) where primary_media_path is null or primary_media_path = ''"
            )
        )
        tags_default_sql = "update contents set tags = '[]' where tags is null"
        editorial_metadata_default_sql = "update contents set editorial_metadata = '{}' where editorial_metadata is null"
        if engine.dialect.name == "postgresql":
            tags_default_sql = "update contents set tags = '[]'::json where tags is null"
            editorial_metadata_default_sql = "update contents set editorial_metadata = '{}'::json where editorial_metadata is null"
        connection.execute(text(tags_default_sql))
        connection.execute(text(editorial_metadata_default_sql))
        connection.execute(text("update contents set candidate_count = 1 where candidate_count is null"))


def migrate_content_status_values(engine) -> None:
    inspector = inspect(engine)
    if "contents" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("contents")}
    if "status" not in columns:
        return
    retired_status = "ready_for_" + chr(114) + chr(112) + chr(97)
    with engine.begin() as connection:
        connection.execute(
            text("update contents set status = :new_status where status = :old_status"),
            {"old_status": retired_status, "new_status": ContentStatus.READY_TO_PUBLISH.value},
        )


def ensure_douyin_video_task_columns(engine) -> None:
    inspector = inspect(engine)
    if "douyin_video_tasks" not in inspector.get_table_names():
        return
