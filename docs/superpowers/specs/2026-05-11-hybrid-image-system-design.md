# Hybrid Image System Design

## Goal

Upgrade the current single-style match poster output into a hybrid image system that:

- keeps the existing local poster renderer as a fallback layer,
- prioritizes real action photos when available,
- uses AI-generated sports-photography-style imagery selectively,
- differentiates WeChat article imagery from Xiaohongshu cover imagery,
- controls API cost through strict per-match and per-run image budgeting.

The first version targets a balanced-cost rollout, not a fully generative system.

## Current State

The current project produces local PNG assets through [images.py](/D:/auto_go/src/auto_football/images.py:17). Those images are:

- structurally stable,
- cheap to generate,
- easy to publish downstream,
- but visually repetitive and too poster-like for both WeChat and Xiaohongshu.

This is especially limiting because:

- WeChat article imagery should feel like sports editorial photography and support reading rhythm.
- Xiaohongshu covers should be more varied and story-driven, not just logo-versus cards.
- Match data is often incomplete, so image generation cannot depend on full structured coverage.

## Product Direction

This design adopts a hybrid, content-led image system.

The system should not assume every match produces the same output shape. Instead, image generation should first determine what kind of image the content needs, then decide whether to use:

1. a real image,
2. an AI-generated sports-photography-style image,
3. a hybrid cover composition,
4. or the existing local template fallback.

## Platform Output Requirements

### WeChat

WeChat should stop behaving like a poster channel.

For each selected match, the target output is:

- 1 hero image at the top of the article,
- 2 to 3 inline images embedded inside the body,
- 1 fallback card available when action imagery is unavailable.

Visual expectations:

- hero image should feel like editorial football coverage,
- inline images should emphasize motion, confrontation, atmosphere, celebration, or frustration,
- large headline text should be minimized,
- information panels should not dominate the image.

Preferred source priority:

1. licensed or legally usable real football photo,
2. AI-generated sports-photography-style action image,
3. minimal fallback card generated locally.

### Xiaohongshu

Xiaohongshu should remain simpler and more flexible.

For the first version:

- 1 cover image is required,
- multi-image output is optional and should not be default,
- the cover may be either a strong-opinion cover, a narrative scene cover, or a hybrid scene-plus-claim cover.

Visual expectations:

- cover should be more click-oriented than WeChat,
- text can be stronger and larger than WeChat,
- output variety matters more than strict editorial realism,
- but it still should not collapse back into the current repetitive logo poster format.

## Visual Strategy

The approved primary direction is:

- `narrative hybrid` as the main system,
- with `strong opinion cover` and `scene illustration` used as sub-variants.

That means the preferred output pattern is:

- imagery first carries atmosphere or conflict,
- a single judgment line may be layered for Xiaohongshu,
- WeChat uses the same scene logic but with much lighter text treatment.

## Image Type Pool

The first version should support this limited image type pool:

### WeChat

- `wechat_hero_scene`
- `wechat_inline_action`
- `wechat_inline_atmosphere`
- `wechat_fallback_card`

### Xiaohongshu

- `xhs_hot_take_cover`
- `xhs_narrative_cover`
- `xhs_result_flash_cover`

This scope is intentionally narrow to preserve control and reduce cost.

## Content-Led Routing

Image output must be driven by content intent rather than raw fixture identity.

The routing layer should evaluate:

- platform,
- content mode (`pre_match`, `result_flash`, `hot_recap`),
- editorial angle,
- data completeness,
- available visual sources,
- remaining image budget.

The routing layer should not decide “which team poster to draw.” It should decide “what visual role this image needs to serve.”

## Visual Brief Layer

Before image generation or retrieval, the system should produce a structured `Visual Brief`.

Suggested fields:

- `platform`
- `slot`
- `image_type`
- `scene_angle`
- `emotion`
- `subject_focus`
- `headline_text`
- `supporting_text`
- `data_dependency`
- `fallback_chain`

This layer becomes the stable internal contract between content generation and image generation.

It allows the project to:

- change models later,
- switch providers later,
- evolve templates later,
- without rewriting content-side logic.

## Content-to-Scene Mapping

The first version should use rules, not an LLM, to map content into visual direction.

Examples:

- `stable favorite / unbeaten angle`
  - scene: pressure, control, forward motion, home advantage
- `even matchup / heavyweight clash`
  - scene: physical confrontation, tactical tension, duels
- `upset warning`
  - scene: underdog resistance, counterattack, goalmouth chaos
- `result flash / hot recap`
  - scene: celebration, collapse, frustration, controversy
- `low data completeness`
  - reduce information dependence,
  - prefer atmosphere or action imagery instead of data cards

## Real Photo Versus AI Usage

The system should follow this priority order:

1. real image if legally usable and structurally suitable,
2. AI-generated sports-photography-style base image,
3. hybrid cover or local fallback card.

Real photos are preferred for WeChat article use because they better match the intended editorial reading experience.

AI imagery is not intended to fully replace all image generation. It is a controlled enhancement layer.

## AI Image Constraints

AI imagery should aim for sports photography realism, not synthetic poster art.

The prompt system should explicitly avoid:

- generated text inside the image,
- watermarks,
- logos,
- visible brand names,
- poster layout baked into the source image,
- extra limbs,
- duplicate balls,
- cartoon or game-render aesthetics,
- excessive neon or fantasy color grading.

AI outputs should primarily be used as clean base imagery for later composition or direct article insertion.

## Cost Strategy

The approved rollout mode is the balanced-cost version.

Rules:

- each match gets at most 1 paid primary image generation by default,
- that generated base image should be reused across WeChat hero and Xiaohongshu cover when possible,
- WeChat inline images should prefer real imagery and only fall back to at most 1 AI action image when necessary,
- Xiaohongshu multi-image output is not enabled by default,
- current local template rendering remains the free fallback layer.

Operational budget guidance for the first version:

- normal daily usage: 3 to 4 paid image calls,
- hard cap: 6 paid image calls per run/day equivalent,
- once the cap is reached, the system must stop calling the provider and fall back locally.

## Failure and Fallback Rules

The fallback order should become more minimal, not more cluttered.

Required fallback chain:

1. real image unavailable,
2. AI image attempt,
3. hybrid cover attempt if applicable,
4. local fallback template.

The system must not default back to the current full-information clutter poster as the preferred fallback for all cases.

## Integration Plan

This design should be integrated with minimal disruption.

### Keep

- existing `GeneratedContent.images` contract,
- existing downstream publisher expectation of local file paths,
- existing `images.py` renderer as the local fallback layer.

### Add

- image provider configuration for Ark,
- a `VisualBriefService`,
- a dedicated Ark image client,
- image routing and budget logic inside the image generation stage.

### Avoid for v1

- full repository-wide image architecture rewrite,
- LLM-written prompt generation per image,
- mandatory multi-image Xiaohongshu carousels,
- a cross-day billing ledger system.

## Security Note

API keys must be read from configuration or environment, not hardcoded into source control by default.

Even if a user temporarily accepts plaintext local configuration during experimentation, the implementation should still support secure environment-based loading as the standard path.

## Success Criteria

The first version is successful if:

- WeChat article imagery no longer defaults to poster-first output,
- Xiaohongshu covers gain obvious visual variety,
- the image system can operate despite incomplete match data,
- paid image generation remains bounded by explicit limits,
- failures gracefully fall back to current local asset generation,
- downstream publishing still works with local image files.
