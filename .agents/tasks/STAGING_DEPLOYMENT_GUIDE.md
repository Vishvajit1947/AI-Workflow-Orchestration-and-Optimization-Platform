# Staging Deployment Quick Start Guide

## Status: ✅ READY FOR STAGING

All blocking issues resolved. Authentication system validated and approved.

---

## Quick Deploy (5 Steps)

### 1. Apply Database Migration
```bash
cd backend
.\venv\Scripts\Activate.ps1
alembic upgrade head
```
**Verify**: `psql -U orchestrator -d ai_orchestrator -c "\dt"` should show `users`, `sessions`, etc.

### 2. Generate Staging Secrets
```bash
# Generate new session secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Copy output for next step.

### 3. Configure Environment
Create `.env` in backend directory:
```bash
ENVIRONMENT=staging
SESSION_SECRET_KEY=<output-from-step-2>
FRONTEND_URL=https://staging.yourdomain.com

# Staging SMTP (example: Mailtrap)
SMTP_HOST=smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=<your-mailtrap-user>
SMTP_PASSWORD=<your-mailtrap-password>
SMTP_FROM_EMAIL=noreply-staging@yourdomain.com

# Staging CORS
CORS_ORIGINS=["https://staging.yourdomain.com"]

# Database (already configured)
DATABASE_URL=<your-staging-db-url>
```

### 4. Start Services
```bash
# Backend
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (new terminal)
cd frontend
npm run build
npm run preview
```

### 5. Smoke Test
```bash
# Health check
curl http://localhost:8000/health

# Auth endpoint (should return 401)
curl http://localhost:8000/api/auth/me
```

---

## Critical Tests (30 minutes)

### Test 1: Registration & Email (5 min)
1. Go to `/signup`
2. Register new account
3. Check email inbox (Mailtrap/staging)
4. **VERIFY**: Email says "expire in 60 minutes" (NOT "15 minutes") ✅
5. Click verification link
6. Should redirect to dashboard

### Test 2: Login & Session (5 min)
1. Go to `/login`
2. Login with verified account
3. **VERIFY**: Redirects to dashboard
4. **VERIFY**: User name shows in sidebar
5. Open DevTools → Application → Cookies
6. **VERIFY**: `session_token` cookie exists
7. **VERIFY**: HttpOnly flag is checked ✅

### Test 3: Password Reset (10 min)
1. Logout
2. Go to `/forgot-password`
3. Enter email address
4. **VERIFY**: Message says "If an account exists..." (non-enumeration) ✅
5. Check email inbox
6. **VERIFY**: Email says "expire in 60 minutes" ✅
7. Click reset link
8. Set new password (min 12 chars)
9. Login with new password
10. Should succeed

### Test 4: Protected Routes (5 min)
1. Logout
2. Type `/dashboard` in address bar
3. **VERIFY**: Redirects to `/login` ✅
4. Login
5. **VERIFY**: Can access all routes ✅

### Test 5: Rate Limiting (5 min)
1. Logout
2. Attempt login with wrong password 15 times rapidly
3. **VERIFY**: After 10 attempts, get "429 Too Many Requests" ✅
4. Wait 60 seconds
5. **VERIFY**: Can attempt login again

---

## Configuration Validation Test

Test that expiry is truly dynamic:

```bash
# 1. Change config
echo "PASSWORD_RESET_EXPIRE_MINUTES=30" >> backend/.env

# 2. Restart backend
# (Ctrl+C and restart uvicorn)

# 3. Request password reset
# Go to /forgot-password and submit

# 4. Check email
# VERIFY: Shows "expire in 30 minutes" (not 60)

# 5. Restore original
echo "PASSWORD_RESET_EXPIRE_MINUTES=60" >> backend/.env
```

**Expected**: Email dynamically reflects configured value ✅

---

## Success Criteria

All tests pass = **APPROVED FOR PRODUCTION PREPARATION**

If any test fails:
1. Check logs: `backend/*.log`
2. Check browser console (F12)
3. Check database: `psql -U orchestrator -d ai_orchestrator`
4. Review error messages

---

## Production Preparation (After Staging Success)

### Required Changes
1. Change `ENVIRONMENT=production`
2. Generate NEW `SESSION_SECRET_KEY`
3. Configure production SMTP (SendGrid/AWS SES)
4. Update `FRONTEND_URL` to production domain
5. Update `CORS_ORIGINS` to production origins
6. Enable HTTPS/TLS
7. Set strong database password

### Security Checklist
- [ ] HTTPS enforced (no HTTP)
- [ ] Production secrets set
- [ ] SMTP configured and tested
- [ ] Database backups enabled
- [ ] Monitoring/alerting configured
- [ ] Error logging configured
- [ ] Rate limits reviewed

---

## Quick Reference

### Important Files Modified
- `backend/app/email_templates/password_reset_email.html` (line 46)
- `backend/app/services/email_service.py` (line 112)

### Key Configuration
- Password reset expiry: **60 minutes** (configurable)
- Email verification expiry: **24 hours**
- Session expiry: **7 days**
- Password minimum: **12 characters**
- Rate limit: **10 requests/minute**

### Endpoints
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `POST /api/auth/verify-email`
- `POST /api/auth/resend-verification`

---

## Support

**Validation Report**: `.agents/tasks/final-auth-validation-report.md`  
**Security Audit**: Run `python backend/security_audit.py`  
**Component Test**: Run `python backend/validate_auth.py`

**Status**: System validated, approved, and ready for staging deployment.
