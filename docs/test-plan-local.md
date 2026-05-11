# Test Plan — PCC AI Portal (Local Dev Environment)
**Version:** 0.1 | **Date:** 2026-05-05 | **Environment:** Docker local

## Scope
ทดสอบ local dev stack ครอบคลุม:
1. Stack startup & health
2. Model routing (3 Claude models)
3. RBAC 5 tiers — model access + token quota
4. Audit log บันทึกถูกต้อง
5. PII detection ภาษาไทย

---

## Prerequisites

```bash
cd workspace/pcc-ai-portal/infrastructure
cp .env.example .env
# แก้ ANTHROPIC_API_KEY ให้ถูกต้อง
docker compose up -d
```

เครื่องมือที่ใช้: `curl`, `jq`, `psql` (หรือ DBeaver)

---

## 1. Stack Startup & Health

### TC-001: ทุก container รัน healthy

```bash
docker compose ps
```

**Expected:** ทุก service status = `healthy`
- pcc-postgres
- pcc-redis
- pcc-litellm
- pcc-open-webui
- pcc-backend

### TC-002: Health endpoints ตอบสนอง

```bash
curl -s http://localhost:4000/health | jq .      # LiteLLM
curl -s http://localhost:8000/health | jq .      # Backend
curl -s http://localhost:3000/health | jq .      # Open WebUI
```

**Expected:** `{"status": "ok"}` หรือ `{"status": "healthy"}` ทุก endpoint

---

## 2. Authentication (Dev Mode)

### TC-010: ขอ token ด้วย dev user สำเร็จ

```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"azure_token": "dev-basic@precise.co.th"}' | jq .
```

**Expected:** `{"access_token": "eyJ...", "token_type": "bearer"}`

### TC-011: token ใช้ดู /auth/me ได้

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"azure_token": "dev-admin@precise.co.th"}' | jq -r .access_token)

curl -s http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected:** `{"tier": "admin", "allowed_models": ["claude-haiku","claude-sonnet","claude-opus"], ...}`

### TC-012: token ไม่ถูกต้อง → 401

```bash
curl -s http://localhost:8000/auth/me \
  -H "Authorization: Bearer invalid-token" | jq .status_code
```

**Expected:** HTTP 401

---

## 3. Model Routing — RBAC

### TC-020: Basic tier เรียก claude-haiku ได้

```bash
# ใช้ key ของ basic user (สร้างผ่าน LiteLLM API)
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-basic-test-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-haiku", "messages": [{"role":"user","content":"hello"}]}' \
  | jq .model
```

**Expected:** `"claude-haiku-4-5-20251001"` (หรือชื่อ model ที่ LiteLLM map)

### TC-021: Basic tier เรียก claude-sonnet → ถูก block

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-basic-test-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet", "messages": [{"role":"user","content":"hello"}]}' \
  | jq .error
```

**Expected:** error message เกี่ยวกับ model not allowed / insufficient permissions

### TC-022: Standard tier เรียก claude-sonnet ได้

**Expected:** response จาก claude-sonnet

### TC-023: Standard tier เรียก claude-opus → ถูก block

**Expected:** error เหมือน TC-021

### TC-024: Pro/Power/Admin เรียก claude-opus ได้

**Expected:** response จาก claude-opus

---

## 4. Token Quota & Rate Limit

### TC-030: เรียก API เกิน rpm_limit → 429

```bash
# ยิง 35 requests ติดกัน (basic limit = 30 rpm)
for i in $(seq 1 35); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    http://localhost:4000/v1/chat/completions \
    -H "Authorization: Bearer sk-basic-test-key" \
    -H "Content-Type: application/json" \
    -d '{"model":"claude-haiku","messages":[{"role":"user","content":"hi"}]}'
done
```

**Expected:** request ที่ 31+ ได้ HTTP 429

### TC-031: ดู spend ปัจจุบันของ user

```bash
curl -s http://localhost:4000/spend/users \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq .
```

**Expected:** JSON แสดง spend, total_tokens ของแต่ละ user

---

## 5. PII Detection ภาษาไทย

### TC-040: ส่งเลขบัตรประชาชน → blocked

```bash
curl -s -X POST http://localhost:8000/guardrails/pii-check \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role":"user","content":"รหัสประชาชนของฉันคือ 1234567890123"}],
    "model": "claude-haiku"
  }' | jq .
```

**Expected:**
```json
{
  "success": false,
  "action": "block",
  "pii_detected": ["thai_national_id"]
}
```

### TC-041: ส่งเบอร์โทรศัพท์ → warned แต่ไม่ block

```bash
curl -s -X POST http://localhost:8000/guardrails/pii-check \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role":"user","content":"ติดต่อได้ที่ 0891234567"}],
    "model": "claude-haiku"
  }' | jq .
```

**Expected:**
```json
{
  "success": true,
  "action": "allow",
  "pii_detected": ["thai_phone"]
}
```

### TC-042: ส่ง text ธรรมดา → allow, no PII

```bash
curl -s -X POST http://localhost:8000/guardrails/pii-check \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role":"user","content":"ช่วยสรุปรายงานประจำปีให้หน่อย"}],
    "model": "claude-haiku"
  }' | jq .
```

**Expected:** `{"success": true, "action": "allow", "pii_detected": []}`

### TC-043: ส่ง prefix ชื่อภาษาไทย → warned

```bash
curl -s -X POST http://localhost:8000/guardrails/pii-check \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role":"user","content":"นาย สมชาย ใจดี ต้องการขอเบิกค่าใช้จ่าย"}],
    "model": "claude-haiku"
  }' | jq .
```

**Expected:** `action: "allow"`, `pii_detected: ["thai_name_prefix"]`

---

## 6. Audit Log

### TC-050: บันทึก audit log ลง PostgreSQL

หลังจาก make request ไป LiteLLM:

```sql
-- เชื่อม psql แล้วรัน
SELECT model, input_tokens, output_tokens, cost_thb, created_at
FROM audit_logs
ORDER BY created_at DESC
LIMIT 5;
```

**Expected:** มี row ใหม่พร้อม model, tokens, cost

### TC-051: audit log ไม่เก็บ content

```sql
-- ตาราง audit_logs ต้องไม่มี column content
\d audit_logs
```

**Expected:** ไม่มี column ชื่อ content, prompt, response

---

## 7. Billing Report

### TC-060: Admin ดู dept report ได้

```bash
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"azure_token": "dev-admin@precise.co.th"}' | jq -r .access_token)

curl -s http://localhost:8000/billing/department \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
```

**Expected:** array ของ department spend พร้อม total_thb

### TC-061: Non-admin ดู dept report → 403

```bash
BASIC_TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"azure_token": "dev-basic@precise.co.th"}' | jq -r .access_token)

curl -s http://localhost:8000/billing/department \
  -H "Authorization: Bearer $BASIC_TOKEN" | jq .detail
```

**Expected:** `"Admin only"`

---

## Test Execution Checklist

| TC | Description | Pass | Fail | Blocked |
|----|-------------|------|------|---------|
| TC-001 | All containers healthy | | | |
| TC-002 | Health endpoints | | | |
| TC-010 | Dev token request | | | |
| TC-011 | /auth/me with token | | | |
| TC-012 | Invalid token → 401 | | | |
| TC-020 | Basic → haiku OK | | | |
| TC-021 | Basic → sonnet blocked | | | |
| TC-022 | Standard → sonnet OK | | | |
| TC-023 | Standard → opus blocked | | | |
| TC-024 | Pro/Power/Admin → opus OK | | | |
| TC-030 | Rate limit 429 | | | |
| TC-031 | Spend API | | | |
| TC-040 | PII block (national ID) | | | |
| TC-041 | PII warn (phone) | | | |
| TC-042 | No PII → allow | | | |
| TC-043 | Thai name prefix → warn | | | |
| TC-050 | Audit log in DB | | | |
| TC-051 | No content in audit | | | |
| TC-060 | Admin dept report | | | |
| TC-061 | Non-admin dept report 403 | | | |

**Pass criteria:** TC-001, TC-002, TC-010, TC-020, TC-021, TC-040, TC-050 ต้องผ่านก่อน demo
