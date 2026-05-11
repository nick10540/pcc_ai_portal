# CLAUDE.md — PCC AI Portal

## Overview
AI Portal สำหรับองค์กร Precise Technology — open-webui + LiteLLM gateway พร้อม RBAC 5 ระดับ

**Goals:** จัดการ LLM access, audit log, PII detection ภาษาไทย, multi-model routing

## Tech Stack
- **Gateway:** LiteLLM (model routing, quota, RBAC)
- **UI:** Open-WebUI
- **DB:** PostgreSQL (audit log, user management)
- **Infra:** Docker Compose

## Commands

```bash
cd infrastructure
cp .env.example .env          # แก้ ANTHROPIC_API_KEY
docker compose up -d          # start all services
docker compose logs -f        # tail logs
docker compose down           # stop
```

## Architecture

```
pcc-ai-portal/
├── infrastructure/    ← Docker Compose + .env config
├── litellm/           ← LiteLLM config (models, routing, RBAC)
├── open-webui/        ← Open-WebUI customization
├── backend/           ← Custom backend extensions
├── database/          ← DB migrations + schema
└── docs/              ← Test plans, architecture docs
```

## RBAC Model
5 tiers — แต่ละ tier มี model access + token quota ต่างกัน  
Config อยู่ใน `litellm/` directory

## Status
- [x] Stack scaffold (docker compose)
- [x] LiteLLM model routing (3 Claude models)
- [x] RBAC 5 tiers design
- [x] Test plan v0.1
- [ ] Audit log implementation
- [ ] PII detection ภาษาไทย
- [ ] Production hardening

## Project Agents
agents อยู่ใน `.claude/agents/` — ใช้ได้ทันที
