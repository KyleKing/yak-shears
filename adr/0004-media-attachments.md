# 0004: Media Attachment Storage and Transcoding

## Status

Accepted (2026-07-04)

## Context

Notes need embedded photos and videos, typically pasted from Apple devices (HEIC images, MOV videos), served efficiently from a small VPS, and stored in the same Syncthing-synced tree as the notes so nothing is lost outside the vault.

## Decision

- Attachments live per-category in `<category>/_attachments/<sha256[:12]>.<ext>`, with thumbnails and video posters in `_attachments/.thumbs/`
- Dedupe is by hash of the original upload bytes, scoped per category (no vault-wide dedupe)
- Everything is transcoded on upload and the original is discarded: HEIC → JPEG and large images downscaled (Pillow + pillow-heif, EXIF transpose); any video → H.264 yuv420p MP4 capped at 1080p with `+faststart`, plus a poster frame (ffmpeg)
- Djot has no video syntax, so videos embed with image syntax `![alt](/media/cat/x.mp4)` and are upgraded client-side (`enhanceMedia()` in editor.js) to `<video preload=none poster=...>`; images swap to lazy-loaded thumbnails linking to full-res
- Upload UX is clipboard paste and a toolbar button only (no drag-drop); root-level notes (no category) reject uploads
- A doctor view reconciles `/media/...` references across `.dj` files against disk: missing files (broken embeds) and orphans (unreferenced)

## Rationale

- Content-hash names make dedupe and cache-busting free; per-category scoping keeps a category self-contained and movable
- Transcoding once at upload beats serving HEIC/MOV that browsers can't render, and discarding originals bounds disk usage on a small VPS
- Client-side video upgrade avoids forking the Djot syntax; Starlette's FileResponse provides Range/206 so seeking works

## Consequences

- ffmpeg is a required system binary in every environment that accepts uploads (must be in cloud-config packages)
- New Python deps: pillow, pillow-heif, filetype (magic-byte sniffing without libmagic)
- Originals are unrecoverable after upload by design
- Doctor is report-only today; orphan deletion is a planned action (PLAN.md Phase 3)
