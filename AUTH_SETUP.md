# Authentication System Setup Guide

Complete setup and configuration guide for the authentication system in the AI Workflow Orchestration Platform.

## Table of Contents

1. [Overview](#overview)
2. [Environment Configuration](#environment-configuration)
3. [Database Setup](#database-setup)
4. [SMTP Configuration](#smtp-configuration)
5. [Development Setup](#development-setup)
6. [Production Deployment](#production-deployment)
7. [Security Considerations](#security-considerations)
8. [Troubleshooting](#troubleshooting)
9. [API Endpoints](#api-endpoints)

---

## Overview

The authentication system provides:

- **Secure user registration** with email verification
- **Session-based authentication** using HTTP-only cookies
- **Password reset** via email tokens
- **Email verification** for new accounts
- **Rate limiting** on sensitive endpoints
- **Argon2id password hashing** for maximum security
- **SHA-256 session token storage** to prevent token leakage

### Technology Stack

- **Backend**: FastAPI with SQLAlchemy 2.0 (async)
- **Frontend**: React 18 with TypeScript
- **Database**: PostgreSQL 15
- **Password Hashing**: Argon2id via passlib
- **Email**: aiosmtplib with Jinja2 templates
- **Rate Limiting**: slowapi

---

## Environment Configuration

### Required Environment Variables

Copy `.env.example` to `.env` and configure the following variables:

#### Database Configuration
```bash
# PostgreSQL connection
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ai_orchestrator
```

#### Authentication & Security
```bash
# Session management
SESSION_SECRET_KEY=your-secure-random-secret-key-min-32-chars
SESSION_EXPIRE_DAYS=7

# Password requirements
PASSWORD_MIN_LENGTH=12
REQUIRE_EMAIL_VERIFICATION=true

# Token expiration
PASSWORD_RESET_EXPIRE_MINUTES=60
EMAIL_VERIFICATION_EXPIRE_HOURS=24
```

#### SMTP Configuration
```bash
# Email service settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=AI Orchestrator

# Frontend URL for email links
FRONTEND_URL=http://localhost:5173
```

#### Application Settings
```bash
# Environment mode
ENVIRONMENT=development  # or 'production'

# CORS configuration
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Generating Secure Keys

Generate a secure `SESSION_SECRET_KEY` using Python:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Or use OpenSSL:

```bash
openssl rand -base64 32
```

---

## Database Setup

### 1. Install PostgreSQL

Ensure PostgreSQL 15+ is installed and running.

### 2. Create Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE ai_orchestrator;

# Create user (if needed)
CREATE USER ai_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ai_orchestrator TO ai_user;
```

### 3. Run Migrations

```bash
cd backend

# Run all migrations including authentication tables
alembic upgrade head
```

This creates the following tables:
- `users` - User accounts
- `sessions` - Active user sessions
- `password_reset_tokens` - Password reset tokens
- `email_verification_tokens` - Email verification tokens

### 4. Verify Migration

```bash
# Connect to database
psql -U ai_user -d ai_orchestrator

# List tables
\dt

# Check users table structure
\d users
```

Expected tables: `users`, `sessions`, `password_reset_tokens`, `email_verification_tokens`, `workflows`, `stages`, `executions`, etc.

---

## SMTP Configuration

### Development Mode (Console Email)

For local development, you can log emails to the console instead of sending them:

1. Leave `SMTP_USER` empty in `.env`:
   ```bash
   SMTP_USER=
   ```

2. Or set `ENVIRONMENT=development`:
   ```bash
   ENVIRONMENT=development
   SMTP_USER=
   ```

Emails will be printed to the backend console with full HTML content.

### Production Mode (Real Email)

#### Using Gmail

1. **Enable 2-Factor Authentication** on your Google account

2. **Generate App Password**:
   - Visit: https://myaccount.google.com/apppasswords
   - Create app password for "Mail"
   - Copy the 16-character password

3. **Configure `.env`**:
   ```bash
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-16-char-app-password
   SMTP_FROM_EMAIL=your-email@gmail.com
   SMTP_FROM_NAME=AI Orchestrator
   ```

#### Using SendGrid

```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=AI Orchestrator
```

#### Using AWS SES

```bash
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=your-aws-ses-access-key
SMTP_PASSWORD=your-aws-ses-secret-key
SMTP_FROM_EMAIL=verified@yourdomain.com
SMTP_FROM_NAME=AI Orchestrator
```

#### Using Mailgun

```bash
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@your-domain.mailgun.org
SMTP_PASSWORD=your-mailgun-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=AI Orchestrator
```

### Email Template Customization

Email templates are located in `backend/app/email_templates/`:

- `verification_email.html` - Email verification template
- `password_reset_email.html` - Password reset template

Edit these files to customize branding, styling, and content. Templates use Jinja2 syntax:

```html
<p>Hello {{ user_name }},</p>
<a href="{{ verification_url }}">Verify Email</a>
```

---

## Development Setup

### Backend

1. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Run migrations**:
   ```bash
   alembic upgrade head
   ```

4. **Start server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Verify API**:
   ```bash
   curl http://localhost:8000/api/health
   ```

### Frontend

1. **Install dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Start development server**:
   ```bash
   npm run dev
   ```

3. **Access application**:
   - Open http://localhost:5173
   - You should see the login page

### Testing Authentication Flow

1. **Register new user**: Visit http://localhost:5173/signup
2. **Check console**: If SMTP is disabled, verification email appears in backend logs
3. **Copy verification link**: Extract token from console output
4. **Verify email**: Visit the verification URL
5. **Login**: Use credentials to sign in
6. **Access dashboard**: Should redirect to main app

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Generate strong `SESSION_SECRET_KEY` (min 32 chars)
- [ ] Configure production database URL
- [ ] Set up real SMTP service (not console logging)
- [ ] Update `FRONTEND_URL` to production domain
- [ ] Update `ALLOWED_ORIGINS` with production URLs
- [ ] Enable HTTPS/TLS
- [ ] Set `PASSWORD_MIN_LENGTH` to 12 or higher
- [ ] Set `REQUIRE_EMAIL_VERIFICATION=true`
- [ ] Configure rate limiting appropriately
- [ ] Set up database backups
- [ ] Configure monitoring and logging

### Environment-Specific Settings

#### Production `.env` Example

```bash
# Application
ENVIRONMENT=production
FRONTEND_URL=https://app.yourdomain.com

# Database
DATABASE_URL=postgresql+asyncpg://user:password@prod-db:5432/ai_orchestrator

# Security
SESSION_SECRET_KEY=<64-char-random-string>
SESSION_EXPIRE_DAYS=7
PASSWORD_MIN_LENGTH=12
REQUIRE_EMAIL_VERIFICATION=true

# SMTP (Production)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=<sendgrid-api-key>
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=AI Orchestrator

# CORS
ALLOWED_ORIGINS=https://app.yourdomain.com
```

### Secure Cookie Settings

In production (`ENVIRONMENT=production`), session cookies are automatically configured with:

- `httponly=True` - JavaScript cannot access cookie
- `secure=True` - Cookie only sent over HTTPS
- `samesite='lax'` - CSRF protection
- `max_age=604800` - 7 days (configurable via SESSION_EXPIRE_DAYS)

### Database Migration in Production

```bash
# Backup database first
pg_dump -U user -d ai_orchestrator > backup_$(date +%Y%m%d).sql

# Run migrations
cd backend
alembic upgrade head

# Verify tables exist
psql -U user -d ai_orchestrator -c "\dt"
```

### Docker Deployment

Example `docker-compose.yml` configuration:

```yaml
services:
  backend:
    build: ./backend
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/ai_orchestrator
      - SESSION_SECRET_KEY=${SESSION_SECRET_KEY}
      - SMTP_HOST=${SMTP_HOST}
      - SMTP_USER=${SMTP_USER}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
      - FRONTEND_URL=https://app.yourdomain.com
    depends_on:
      - db
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    environment:
      - VITE_API_URL=https://api.yourdomain.com
    ports:
      - "3000:80"

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=ai_orchestrator
      - POSTGRES_PASSWORD=secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Security Considerations

### Password Security

- **Hashing**: Argon2id algorithm (current industry standard)
- **Minimum length**: 12 characters (configurable)
- **Strength validation**: Frontend provides real-time feedback
- **No plaintext storage**: Passwords are never stored in plaintext

### Session Security

- **Token generation**: Cryptographically secure random tokens (32 bytes)
- **Token storage**: SHA-256 hashed in database (plaintext never stored)
- **Token comparison**: Timing-safe comparison prevents side-channel attacks
- **Cookie security**: HTTP-only, secure (in production), SameSite=lax
- **Session expiration**: Configurable (default 7 days)

### Rate Limiting

The following endpoints are rate-limited to **10 requests per minute**:

- `/api/auth/register`
- `/api/auth/login`
- `/api/auth/forgot-password`
- `/api/auth/resend-verification`

Adjust rate limits in `backend/app/api/auth.py` if needed:

```python
@limiter.limit("10/minute")  # Change to "5/minute" or "20/minute"
```

### Email Security

- **Non-enumeration**: Forgot password always returns same message
- **Token expiration**: Reset tokens expire after 60 minutes (configurable)
- **Verification expiration**: Verification tokens expire after 24 hours (configurable)
- **Normalized emails**: All emails stored and compared in lowercase

### CORS Configuration

Configure `ALLOWED_ORIGINS` to restrict which domains can access your API:

```bash
# Development
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Production
ALLOWED_ORIGINS=https://app.yourdomain.com,https://www.yourdomain.com
```

### Additional Hardening

1. **Use HTTPS**: Always use TLS in production
2. **Enable HSTS**: Add Strict-Transport-Security header
3. **CSP Headers**: Configure Content Security Policy
4. **Database security**: Use strong passwords, restrict network access
5. **Regular updates**: Keep dependencies up to date
6. **Audit logging**: Monitor authentication events
7. **Backup strategy**: Regular encrypted backups
8. **Secrets management**: Use vault services (AWS Secrets Manager, HashiCorp Vault)

---

## Troubleshooting

### Issue: "Invalid credentials" on login

**Symptoms**: Users cannot login with correct password

**Solutions**:
1. Verify password was set correctly during registration
2. Check database password hash exists: `SELECT email, password_hash FROM users;`
3. Test password verification manually:
   ```python
   from backend.app.core.security import verify_password
   verify_password("user_password", "stored_hash")
   ```
4. Ensure email normalization is consistent (lowercase)

### Issue: Session cookie not persisted

**Symptoms**: Users logged out immediately after login

**Solutions**:
1. Check `withCredentials: true` in frontend `api.ts`
2. Verify CORS allows credentials: `allow_credentials=True` in backend
3. Check cookie domain/path configuration
4. Inspect browser cookies in DevTools
5. Verify `SESSION_SECRET_KEY` is set and consistent

### Issue: Emails not sending

**Symptoms**: No verification or reset emails received

**Solutions**:

**Development mode**:
1. Check if `SMTP_USER` is empty (console logging enabled)
2. Look for email content in backend console logs
3. Check for errors in logs

**Production mode**:
1. Verify SMTP credentials are correct
2. Test SMTP connection:
   ```python
   import asyncio
   import aiosmtplib
   from email.message import EmailMessage
   
   async def test_smtp():
       msg = EmailMessage()
       msg["From"] = "your-email@gmail.com"
       msg["To"] = "test@example.com"
       msg["Subject"] = "Test"
       msg.set_content("Test message")
       
       await aiosmtplib.send(
           msg,
           hostname="smtp.gmail.com",
           port=587,
           username="your-email@gmail.com",
           password="your-app-password",
           start_tls=True
       )
   
   asyncio.run(test_smtp())
   ```
3. Check spam folder
4. Verify `SMTP_FROM_EMAIL` is authorized to send (SPF/DKIM/DMARC)
5. Check SMTP provider rate limits

### Issue: "Token expired" on email verification

**Symptoms**: Verification links don't work

**Solutions**:
1. Check `EMAIL_VERIFICATION_EXPIRE_HOURS` setting
2. Verify system clock is synchronized
3. Generate new verification token: Visit `/verify-email` and click "Resend"
4. Check token exists in database: `SELECT * FROM email_verification_tokens;`

### Issue: 401 Unauthorized on protected routes

**Symptoms**: Logged-in users redirected to login

**Solutions**:
1. Check session cookie exists in browser DevTools
2. Verify session exists in database: `SELECT * FROM sessions WHERE user_id='...'`
3. Check session expiration: `SELECT expires_at FROM sessions WHERE user_id='...'`
4. Verify `get_current_user` dependency receives cookie
5. Check axios interceptor is not clearing cookies

### Issue: TypeScript errors in frontend

**Symptoms**: Frontend build fails with type errors

**Solutions**:
1. Run type check: `cd frontend && npx tsc --noEmit`
2. Verify all imports exist
3. Check `types/auth.ts` exports are correct
4. Ensure no `any` types in catch blocks (use `unknown`)

### Issue: Database migration fails

**Symptoms**: `alembic upgrade head` errors

**Solutions**:
1. Check current revision: `alembic current`
2. View migration history: `alembic history`
3. Downgrade one revision: `alembic downgrade -1`
4. Check database connection: `psql -U user -d ai_orchestrator`
5. Verify previous migrations ran successfully
6. Check for conflicting table/column names

### Issue: Rate limit errors

**Symptoms**: "429 Too Many Requests" errors

**Solutions**:
1. Wait 1 minute before retrying
2. Adjust rate limits in `backend/app/api/auth.py`
3. Configure slowapi storage backend for distributed systems
4. Check if multiple requests are being sent accidentally

### Debug Mode

Enable debug logging for troubleshooting:

```python
# In backend/app/main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

View detailed logs:
```bash
# Backend logs
tail -f backend/logs/app.log

# Database queries
export SQLALCHEMY_ECHO=True
```

---

## API Endpoints

### Authentication Endpoints

#### POST `/api/auth/register`
Register a new user account.

**Request body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "John Doe",
  "terms_accepted": true
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_email_verified": false,
  "is_active": true,
  "role": "user",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Rate limit**: 10 requests/minute

---

#### POST `/api/auth/login`
Authenticate user and create session.

**Request body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "remember_me": false
}
```

**Response** (200 OK):
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_email_verified": true,
  "is_active": true,
  "role": "user",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Sets cookie**: `session_token` (HTTP-only, secure in production)

**Rate limit**: 10 requests/minute

---

#### POST `/api/auth/logout`
Revoke current session.

**Headers**: Requires `session_token` cookie

**Response** (200 OK):
```json
{
  "message": "Logged out successfully"
}
```

**Clears cookie**: `session_token`

---

#### GET `/api/auth/me`
Get current authenticated user.

**Headers**: Requires `session_token` cookie

**Response** (200 OK):
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_email_verified": true,
  "is_active": true,
  "role": "user",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

#### POST `/api/auth/forgot-password`
Request password reset email.

**Request body**:
```json
{
  "email": "user@example.com"
}
```

**Response** (200 OK):
```json
{
  "message": "If an account exists for this email, password reset instructions have been sent"
}
```

**Note**: Always returns same message (non-enumeration)

**Rate limit**: 10 requests/minute

---

#### POST `/api/auth/reset-password`
Reset password using token from email.

**Request body**:
```json
{
  "token": "secure-reset-token-from-email",
  "new_password": "NewSecurePassword123!"
}
```

**Response** (200 OK):
```json
{
  "message": "Password reset successfully"
}
```

**Errors**:
- 400: Token expired or invalid
- 400: Password too short

---

#### POST `/api/auth/verify-email`
Verify email using token from email.

**Request body**:
```json
{
  "token": "secure-verification-token-from-email"
}
```

**Response** (200 OK):
```json
{
  "message": "Email verified successfully"
}
```

**Errors**:
- 400: Token expired or invalid
- 400: Email already verified

---

#### POST `/api/auth/resend-verification`
Resend email verification link.

**Headers**: Requires `session_token` cookie

**Response** (200 OK):
```json
{
  "message": "Verification email sent"
}
```

**Errors**:
- 400: Email already verified

**Rate limit**: 10 requests/minute

---

## Additional Resources

### Documentation
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic Migrations](https://alembic.sqlalchemy.org/en/latest/)
- [OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

### Security Best Practices
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Argon2 Specification](https://github.com/P-H-C/phc-winner-argon2)
- [Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)

### Support
For issues or questions:
1. Check this documentation
2. Review troubleshooting section
3. Check application logs
4. Consult project README.md

---

**Last Updated**: 2024-01-15  
**Version**: 1.0.0
