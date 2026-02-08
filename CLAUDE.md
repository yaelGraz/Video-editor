# Project: AI Video -> Video (Subtitles + Music) with Visual UI

We are building a web app where a user uploads a video and receives a final edited video:
- Accurate subtitles (VTT/SRT) + optionally burned-in subtitles
- Background music selected to match the video (and improved over time with feedback)
- Final MP4 output ready to download
Everything is managed from a clean visual interface.

## Stack (preferred)
- Next.js (App Router) + TypeScript for UI + API routes
- Node.js Worker (job processing)
- PostgreSQL + Prisma (data)
- Redis + BullMQ (queues)
- FFmpeg (media processing)
- Object storage for files (local dev folder, production S3/R2-compatible)

## Core User Flow (must support)
1) Upload video in the UI
2) Create a processing Job and show progress in UI
3) Generate transcript and subtitles (VTT/SRT)
4) Select background music that matches the video
5) Mix audio (duck music under speech) + normalize loudness
6) Render final MP4
7) Show preview + download link in UI
8) Collect user feedback (like/dislike + “more calm / more energetic / etc.”)

## “Gets smarter over time” requirement
We do NOT train a music model from scratch in v1.
Instead implement learning via:
- Brand/Profile settings per user (style preferences)
- Feedback-driven re-ranking / scoring weights
- Store every selection + feedback for continuous improvement

Data tables to include (minimum):
- VideoJob (status, progress, inputUrl, outputUrl, subtitlesUrl, chosenTrackId, error)
- MusicTrack (tags: mood, bpm, energy, genre, instruments, length)
- BrandProfile (weights/preferences)
- Feedback (jobId, userId, rating, notes, adjustments)

## Worker Pipeline Requirements
Implement a modular pipeline with clear stages and logs:
- Download input
- Extract audio (wav)
- Transcribe -> produce VTT/SRT
- (optional) Burn subtitles into video OR attach subtitles track
- Choose music track using `selectTrack(videoFeatures, brandProfile)`
- Mix: ducking under speech + normalize
- Export MP4
- Upload outputs and update progress

## UI Requirements (visual)
Must have 3 screens:
- Upload + style preset selector
- Job status/progress page (polling or SSE)
- Result page: video preview + download + feedback buttons

## Coding Rules
- TypeScript everywhere
- Do not break existing APIs; version endpoints if needed
- Keep functions small and composable; worker pipeline in separate modules
- Always add migrations for Prisma schema changes
- Add minimal tests for key logic (track selection + job status transitions)
- Add clear error handling + job failure reporting

## Local Dev
- Provide docker-compose for Postgres + Redis
- Provide npm scripts to run web + worker
- Keep FFmpeg dependency documented (or use a Docker image for worker)

## Commands
- npm run dev
- npm run build
- npm run lint
- npm run test
