# Authentication System Implementation Plan

## Project Context

**Backend Stack:** FastAPI 0.115.6, Python 3.11+, SQLAlchemy 2.0.36 (async), Alembic, PostgreSQL 15, asyncpg
**Frontend Stack:** React 18, TypeScript, Vite 5.4.1, Tailwind CSS 3.4.10, React Router v6, Axios
**Database ORM:** SQLAlchemy async with DeclarativeBase from backend/app/database.py
**Existing Patterns:**
- Models: UUID pk with `server_default=func.gen_random_uuid()`, `mapped_column`, `Mapped` types
- Schemas: Pydantic v2 `BaseModel`, `Field`, `model_config = {"from_attributes": True}`
- API: `APIRouter(prefix="/...")`, `Depends(get_db)` yielding AsyncSession
- API aggregation: backend/app/api/__init__.py includes all routers into api_router with prefix /api
- CORS: already configured in main.py with `allow_credentials=True`
- Frontend API: frontend/src/lib/api.ts uses axios with baseURL pointing to /api
- Theme: Tailwind dark theme with emerald primary colors (primary-400: #3ecf8e, primary-500: #24b47e, primary-600: #006239)
- Current workflow: NO authentication exists anywhere in the codebase

---

## Implementation Plan

### PRIORITY 1: Database Models + Migration

- [ ] 1. Create User model in `backend/app/models/user.py`
      
      **What:** Define the User ORM model with UUID primary key, authentication fields, and audit timestamps. Follow existing pattern from workflow.py: use `mapped_column`, `Mapped` types, `UUID(as_uuid=True)` with `server_default=func.gen_random_uuid()`, `DateTime(timezone=True)` with `server_default=func.now()`.
      
      **Fields:**
      - `id`: UUID primary key with server_default gen_random_uuid()
      - `email`: String(255), unique, not null, indexed
      - `email_normalized`: String(255), unique, not null, indexed (lowercase version for case-insensitive lookups)
      - `password_hash`: String(255), not null (Argon2 hash)
      - `full_name`: String(255), not null
      - `is_email_verified`: Boolean, default False
      - `is_active`: Boolean, default True
      - `role`: String(50), default "user" (future: "admin", "user")
      - `created_at`: DateTime(timezone=True), server_default now()
      - `updated_at`: DateTime(timezone=True), server_default now(), onupdate now()
      
      **Relationships:** Add `sessions`, `password_reset_tokens`, `email_verification_tokens` relationships (back_populates, cascade="all, delete-orphan")
      
      **Files:** `backend/app/models/user.py`
      
      **Verify:** Read the file and confirm all fields match the pattern from workflow.py; check relationships are defined correctly.

- [ ] 2. Create Session model in `backend/app/models/session.py`
      
      **What:** Define the Session ORM model for managing user sessions stored in the database (cookie-based authentication).
      
      **Fields:**
      - `id`: UUID primary key with server_default gen_random_uuid()
      - `user_id`: UUID, ForeignKey('users.id', ondelete='CASCADE'), not null, indexed
      - `session_token`: String(255), unique, not null, indexed (SHA-256 hash of secure random token)
      - `expires_at`: DateTime(timezone=True), not null, indexed
      - `created_at`: DateTime(timezone=True), server_default now()
      - `last_used_at`: DateTime(timezone=True), nullable (updated on each request)
      
      **Relationships:** `user` relationship to User model with back_populates
      
      **Files:** `backend/app/models/session.py`
      
      **Verify:** Read the file and confirm FK constraint matches Alembic pattern from 001_initial migration; check relationship to User.

- [ ] 3. Create PasswordResetToken model in `backend/app/models/password_reset.py`
      
      **What:** Define the PasswordResetToken model for secure password reset flow.
      
      **Fields:**
      - `id`: UUID primary key with server_default gen_random_uuid()
      - `user_id`: UUID, ForeignKey('users.id', ondelete='CASCADE'), not null, indexed
      - `token_hash`: String(255), unique, not null, indexed (SHA-256 hash of secure random token)
      - `expires_at`: DateTime(timezone=True), not null, indexed
      - `used`: Boolean, default False, not null
      - `created_at`: DateTime(timezone=True), server_default now()
      
      **Relationships:** `user` relationship to User model with back_populates
      
      **Files:** `backend/app/models/password_reset.py`
      
      **Verify:** Read the file and confirm used flag prevents token reuse; check expiration logic is enforceable.

- [ ] 4. Create EmailVerificationToken model in `backend/app/models/email_verification.py`
      
      **What:** Define the EmailVerificationToken model for email verification flow (same pattern as PasswordResetToken).
      
      **Fields:** Same as PasswordResetToken (id, user_id, token_hash, expires_at, used, created_at)
      
      **Relationships:** `user` relationship to User model with back_populates
      
      **Files:** `backend/app/models/email_verification.py`
      
      **Verify:** Read the file and confirm it matches PasswordResetToken structure.

- [ ] 5. Update models __init__.py to export all new models
      
      **What:** Import and export User, Session, PasswordResetToken, EmailVerificationToken in `backend/app/models/__init__.py` so Alembic can auto-detect them via Base.metadata. Follow existing pattern where all models are imported at the top and listed in __all__.
      
      **Files:** `backend/app/models/__init__.py`
      
      **Verify:** Read the file and confirm new models are imported and listed in __all__ alongside existing models.

- [ ] 6. Create Alembic migration for auth tables
      
      **What:** Generate a new Alembic migration to create `users`, `sessions`, `password_reset_tokens`, `email_verification_tokens` tables, plus add a nullable `user_id` foreign key column to the `workflows` table (for multi-tenancy).
      
      **Migration conventions from 001_initial:**
      - Use `postgresql.UUID(as_uuid=True)` for UUID columns
      - Use `server_default=sa.text('gen_random_uuid()')` for UUID primary keys
      - Use `server_default=sa.text('now()')` for timestamps
      - Use `sa.ForeignKeyConstraint([column], [table.column], ondelete='CASCADE')` for foreign keys
      - Create indexes on foreign keys, unique fields, and frequently queried columns (email_normalized, session_token, token_hash, expires_at)
      
      **Tables to create:**
      1. `users` (columns as in step 1, unique constraints on email and email_normalized, indexes on email_normalized)
      2. `sessions` (columns as in step 2, indexes on user_id, session_token, expires_at)
      3. `password_reset_tokens` (columns as in step 3, indexes on user_id, token_hash, expires_at)
      4. `email_verification_tokens` (columns as in step 4, indexes on user_id, token_hash, expires_at)
      5. Alter `workflows` table: add nullable `user_id` UUID column with FK to users.id (ondelete='SET NULL' to preserve workflows if user deleted)
      
      **Commands:**
      ```bash
      cd backend
      alembic revision -m "add_auth_tables_and_user_workflows"
      # Edit the generated file in backend/alembic/versions/ following the conventions above
      ```
      
      **Files:** `backend/alembic/versions/XXX_add_auth_tables_and_user_workflows.py`
      
      **Verify:** Run `cd backend && alembic upgrade head` and confirm migration applies without errors. Check tables exist in the database with correct columns, constraints, and indexes.

---

### PRIORITY 2: Backend Security Utilities + Services

- [ ] 7. Create core package and security utilities in `backend/app/core/security.py`
      
      **What:** Implement password hashing (Argon2 via passlib), secure token generation (secrets module), SHA-256 token hashing, and timing-safe comparison utilities.
      
      **Functions:**
      - `hash_password(password: str) -> str`: Hash password using Argon2id via passlib CryptContext
      - `verify_password(plain_password: str, hashed_password: str) -> bool`: Verify password against hash
      - `generate_secure_token(nbytes: int = 32) -> str`: Generate URL-safe random token (secrets.token_urlsafe)
      - `hash_token(token: str) -> str`: SHA-256 hash a token for database storage
      - `verify_token_hash(token: str, token_hash: str) -> bool`: Timing-safe comparison of token hash
      
      **Dependencies:** passlib[argon2], hashlib, secrets, hmac (for timing-safe comparison)
      
      **Files:** `backend/app/core/__init__.py` (empty), `backend/app/core/security.py`
      
      **Verify:** Import functions in a Python REPL and test: hash_password returns Argon2 hash starting with $argon2id$, verify_password validates correctly, generate_secure_token returns 43-char string, hash_token returns 64-char hex digest.

- [ ] 8. Create authentication service in `backend/app/services/auth_service.py`
      
      **What:** Implement user registration, login, password reset, and email verification logic. All functions async, accept AsyncSession.
      
      **Functions:**
      - `register_user(db: AsyncSession, email: str, password: str, full_name: str) -> User`: Validate email uniqueness (case-insensitive), hash password, create user with is_email_verified=False, create email verification token, return user
      - `authenticate_user(db: AsyncSession, email: str, password: str) -> User | None`: Find user by email_normalized, verify password, check is_active, return user or None
      - `create_password_reset_token(db: AsyncSession, email: str) -> str | None`: Find user by email_normalized, create PasswordResetToken with secure token and expiry (15 minutes from config), return plain token or None if user not found (non-enumeration)
      - `verify_reset_token(db: AsyncSession, token: str) -> User | None`: Hash token, find matching PasswordResetToken, check not used and not expired, return user or None
      - `reset_password(db: AsyncSession, token: str, new_password: str) -> bool`: Verify token, update user password hash, mark token as used, return success bool
      - `create_verification_token(db: AsyncSession, user_id: uuid.UUID) -> str`: Create EmailVerificationToken with secure token and expiry (24 hours from config), return plain token
      - `verify_email(db: AsyncSession, token: str) -> bool`: Hash token, find matching EmailVerificationToken, check not used and not expired, update user.is_email_verified=True, mark token as used, return success bool
      
      **Error Handling:** Raise HTTPException with appropriate status codes (400 for validation, 409 for duplicate email)
      
      **Files:** `backend/app/services/auth_service.py`
      
      **Verify:** Write unit tests in backend/tests/unit/test_auth_service.py covering all functions, especially edge cases (expired token, used token, non-existent user, duplicate email).

- [ ] 9. Create session service in `backend/app/services/session_service.py`
      
      **What:** Implement session management for cookie-based authentication. All functions async, accept AsyncSession.
      
      **Functions:**
      - `create_session(db: AsyncSession, user_id: uuid.UUID, expires_in_days: int = 7) -> tuple[Session, str]`: Generate secure token, hash it, create Session record with expiry, return (Session, plain_token)
      - `validate_session(db: AsyncSession, session_token: str) -> User | None`: Hash token, find matching Session, check not expired, update last_used_at, load and return user (with is_active check) or None
      - `refresh_session(db: AsyncSession, session_token: str, expires_in_days: int = 7) -> Session | None`: Validate session, extend expires_at by expires_in_days, return updated Session or None
      - `revoke_session(db: AsyncSession, session_token: str) -> bool`: Hash token, delete matching Session, return success bool
      - `revoke_all_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> int`: Delete all sessions for user, return count
      
      **Session Lifecycle:** Sessions expire after SESSION_EXPIRE_DAYS (default 7), last_used_at updated on each request, expired sessions cleaned up periodically
      
      **Files:** `backend/app/services/session_service.py`
      
      **Verify:** Write unit tests covering create, validate (fresh + expired + invalid), refresh, revoke (single + all).

- [ ] 10. Create email service in `backend/app/services/email_service.py`
      
      **What:** Implement email sending with aiosmtplib for async SMTP. In development mode (ENVIRONMENT=development), log emails to console instead of sending. Use Jinja2 templates for email HTML.
      
      **Functions:**
      - `send_email(to_email: str, subject: str, html_body: str, text_body: str) -> bool`: Send email via SMTP (or log in dev mode), return success bool
      - `send_verification_email(to_email: str, full_name: str, token: str) -> bool`: Render verification email template with link to {FRONTEND_URL}/verify-email?token={token}, call send_email
      - `send_password_reset_email(to_email: str, full_name: str, token: str) -> bool`: Render password reset email template with link to {FRONTEND_URL}/reset-password?token={token}, call send_email
      
      **Configuration (from settings):** SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL, SMTP_FROM_NAME, FRONTEND_URL, ENVIRONMENT
      
      **Dev Mode:** When ENVIRONMENT=development, print formatted email to console with [DEV EMAIL] prefix, return True (do not connect to SMTP)
      
      **Files:** `backend/app/services/email_service.py`, `backend/app/email_templates/verification_email.html`, `backend/app/email_templates/password_reset_email.html`
      
      **Email Template Structure:** Clean HTML with emerald brand color (#3ecf8e), centered layout, CTA button, plain text fallback
      
      **Verify:** Call send_verification_email in dev mode and confirm console output shows formatted email with correct token link. In production, test with a real SMTP server (e.g., Mailtrap).

- [ ] 11. Create authentication dependencies in `backend/app/core/dependencies.py`
      
      **What:** Define FastAPI dependencies for protected routes: get_current_user (from session cookie), get_current_active_user, get_current_verified_user.
      
      **Functions:**
      - `get_current_user(session_token: str = Cookie(None, alias="session"), db: AsyncSession = Depends(get_db)) -> User`: Read session cookie, validate via session_service.validate_session, return user or raise 401 HTTPException
      - `get_current_active_user(current_user: User = Depends(get_current_user)) -> User`: Check current_user.is_active, return user or raise 403 HTTPException
      - `get_current_verified_user(current_user: User = Depends(get_current_active_user)) -> User`: Check current_user.is_email_verified or settings.REQUIRE_EMAIL_VERIFICATION=False, return user or raise 403 HTTPException with "Email verification required" message
      
      **Cookie Name:** "session" (httponly, secure in production, samesite=lax)
      
      **Error Messages:** 401 "Not authenticated", 403 "Account inactive" or "Email verification required"
      
      **Files:** `backend/app/core/dependencies.py`
      
      **Verify:** Write integration tests that call protected endpoints without cookie (expect 401), with invalid cookie (expect 401), with valid cookie for inactive user (expect 403).

- [ ] 12. Add authentication dependencies to requirements.txt
      
      **What:** Add passlib[argon2], python-jose[cryptography], aiosmtplib, jinja2, slowapi to requirements.txt with pinned versions.
      
      **Dependencies:**
      ```
      passlib[argon2]==1.7.4
      python-jose[cryptography]==3.3.0
      aiosmtplib==3.0.2
      jinja2==3.1.4
      slowapi==0.1.9
      ```
      
      **Files:** `backend/requirements.txt`
      
      **Verify:** Run `pip install -r backend/requirements.txt` and confirm all packages install without errors.

---

### PRIORITY 3: Backend API Endpoints

- [ ] 13. Create auth schemas in `backend/app/schemas/auth.py`
      
      **What:** Define Pydantic v2 request/response schemas for authentication endpoints. Follow existing schema patterns from workflow.py and stage.py.
      
      **Schemas:**
      - `RegisterRequest(BaseModel)`: email (EmailStr), password (str, min_length from config), full_name (str, min_length=1), terms_accepted (bool, must be True)
      - `LoginRequest(BaseModel)`: email (EmailStr), password (str), remember_me (bool, default False)
      - `UserResponse(BaseModel)`: id (uuid.UUID), email (str), full_name (str), is_email_verified (bool), is_active (bool), role (str), created_at (datetime), model_config from_attributes
      - `ForgotPasswordRequest(BaseModel)`: email (EmailStr)
      - `ResetPasswordRequest(BaseModel)`: token (str), new_password (str, min_length from config)
      - `VerifyEmailRequest(BaseModel)`: token (str)
      - `MessageResponse(BaseModel)`: message (str)
      
      **Validation:** Use Pydantic validators for password strength (min length, complexity), email format, terms acceptance
      
      **Files:** `backend/app/schemas/auth.py`
      
      **Verify:** Import schemas and validate sample data with valid/invalid inputs; confirm validation errors are raised appropriately.

- [ ] 14. Create auth router in `backend/app/api/auth.py`
      
      **What:** Implement authentication REST API endpoints with rate limiting (slowapi). Follow existing API patterns from workflows.py.
      
      **Endpoints:**
      - `POST /auth/register`: Accept RegisterRequest, call auth_service.register_user, send verification email, return 201 with UserResponse and message "Please check your email to verify your account"
      - `POST /auth/login`: Accept LoginRequest, call auth_service.authenticate_user (return 401 if None), create session via session_service.create_session (remember_me determines expires_in_days: 30 if True else 7), set httponly cookie with session token, return UserResponse
      - `POST /auth/logout`: Require get_current_user dependency, revoke session via session_service.revoke_session, clear session cookie (set max_age=0), return MessageResponse "Logged out successfully"
      - `GET /auth/me`: Require get_current_user dependency, return UserResponse with current user
      - `POST /auth/forgot-password`: Accept ForgotPasswordRequest, call auth_service.create_password_reset_token (non-enumeration: always return same message), send password reset email, return MessageResponse "If an account exists for this email, password reset instructions have been sent"
      - `POST /auth/reset-password`: Accept ResetPasswordRequest, call auth_service.reset_password (return 400 if token invalid/expired), return MessageResponse "Password reset successfully"
      - `POST /auth/verify-email`: Accept VerifyEmailRequest, call auth_service.verify_email (return 400 if token invalid/expired), return MessageResponse "Email verified successfully"
      - `POST /auth/resend-verification`: Require get_current_user dependency, check not already verified, call auth_service.create_verification_token, send verification email, return MessageResponse "Verification email sent"
      
      **Cookie Configuration:** httponly=True, secure=(ENVIRONMENT=="production"), samesite="lax", path="/", max_age=SESSION_EXPIRE_DAYS*86400
      
      **Rate Limiting:** Use slowapi to limit auth endpoints to 10 requests per minute per IP (register, login, forgot-password, resend-verification)
      
      **Files:** `backend/app/api/auth.py`
      
      **Verify:** Write integration tests in backend/tests/integration/test_auth_api.py covering full flows: register → login → me (with cookie) → logout → me (401), forgot-password → reset-password → login with new password, verify-email with valid/expired/invalid token, rate limiting triggers 429 after 10 requests.

- [ ] 15. Update API router aggregation to include auth router
      
      **What:** Import and include auth_router in backend/app/api/__init__.py following existing pattern.
      
      **Code Change:** Add `from backend.app.api.auth import router as auth_router` and `api_router.include_router(auth_router)` in the appropriate position (after imports, before other includes)
      
      **Files:** `backend/app/api/__init__.py`
      
      **Verify:** Start the backend server and navigate to http://localhost:8000/docs; confirm /api/auth/* endpoints are listed in Swagger UI.

---

### PRIORITY 4: Backend Configuration

- [ ] 16. Update config.py with authentication settings
      
      **What:** Add all authentication-related environment variables to backend/app/config.py following existing Settings class pattern.
      
      **New Settings:**
      ```python
      # Authentication
      SESSION_SECRET_KEY: str = Field(default="change-me-in-production", description="Secret for signing session tokens")
      SESSION_EXPIRE_DAYS: int = Field(default=7, description="Session cookie lifetime in days")
      REQUIRE_EMAIL_VERIFICATION: bool = Field(default=True, description="Require email verification to access protected routes")
      PASSWORD_MIN_LENGTH: int = Field(default=8, description="Minimum password length")
      PASSWORD_RESET_EXPIRE_MINUTES: int = Field(default=15, description="Password reset token lifetime")
      EMAIL_VERIFICATION_EXPIRE_HOURS: int = Field(default=24, description="Email verification token lifetime")
      
      # SMTP
      SMTP_HOST: str = Field(default="localhost", description="SMTP server host")
      SMTP_PORT: int = Field(default=587, description="SMTP server port")
      SMTP_USER: Optional[str] = Field(default=None, description="SMTP username")
      SMTP_PASSWORD: Optional[str] = Field(default=None, description="SMTP password")
      SMTP_FROM_EMAIL: str = Field(default="noreply@example.com", description="From email address")
      SMTP_FROM_NAME: str = Field(default="AI Orchestrator", description="From name")
      
      # Frontend
      FRONTEND_URL: str = Field(default="http://localhost:5173", description="Frontend URL for email links")
      ```
      
      **Files:** `backend/app/config.py`
      
      **Verify:** Read config.py and confirm all new fields are added with types, defaults, and descriptions matching the pattern of existing settings.

- [ ] 17. Update .env.example with authentication variables
      
      **What:** Add all new authentication environment variables to .env.example with example values and comments.
      
      **New Variables:**
      ```env
      # ---------- Authentication ----------
      SESSION_SECRET_KEY=change-me-in-production-use-secrets-token-hex-32
      SESSION_EXPIRE_DAYS=7
      REQUIRE_EMAIL_VERIFICATION=true
      PASSWORD_MIN_LENGTH=8
      PASSWORD_RESET_EXPIRE_MINUTES=15
      EMAIL_VERIFICATION_EXPIRE_HOURS=24
      
      # ---------- SMTP (Email) ----------
      # For development, emails are logged to console. For production, configure SMTP.
      SMTP_HOST=smtp.gmail.com
      SMTP_PORT=587
      SMTP_USER=your-email@gmail.com
      SMTP_PASSWORD=your-app-password
      SMTP_FROM_EMAIL=noreply@orchestrator.example.com
      SMTP_FROM_NAME=AI Orchestrator
      
      # ---------- Frontend URL ----------
      FRONTEND_URL=http://localhost:5173
      ```
      
      **Files:** `.env.example`
      
      **Verify:** Read .env.example and confirm all auth variables are documented with helpful comments.

---

### PRIORITY 5: Frontend Types + API Client

- [ ] 18. Create auth types in `frontend/src/types/auth.ts`
      
      **What:** Define TypeScript types for authentication data matching backend schemas.
      
      **Types:**
      ```typescript
      export interface User {
        id: string;
        email: string;
        full_name: string;
        is_email_verified: boolean;
        is_active: boolean;
        role: string;
        created_at: string;
      }
      
      export interface RegisterData {
        email: string;
        password: string;
        full_name: string;
        terms_accepted: boolean;
      }
      
      export interface LoginData {
        email: string;
        password: string;
        remember_me?: boolean;
      }
      
      export interface ForgotPasswordData {
        email: string;
      }
      
      export interface ResetPasswordData {
        token: string;
        new_password: string;
      }
      
      export interface VerifyEmailData {
        token: string;
      }
      
      export interface AuthResponse {
        message?: string;
        user?: User;
      }
      ```
      
      **Files:** `frontend/src/types/auth.ts`
      
      **Verify:** Import types in a TypeScript file and confirm no compilation errors.

- [ ] 19. Create auth API client in `frontend/src/api/authApi.ts`
      
      **What:** Implement authentication API functions using the existing axios instance from lib/api.ts.
      
      **Functions:**
      - `register(data: RegisterData): Promise<AuthResponse>`: POST /auth/register
      - `login(data: LoginData): Promise<User>`: POST /auth/login
      - `logout(): Promise<void>`: POST /auth/logout
      - `getCurrentUser(): Promise<User>`: GET /auth/me
      - `forgotPassword(data: ForgotPasswordData): Promise<{ message: string }>`: POST /auth/forgot-password
      - `resetPassword(data: ResetPasswordData): Promise<{ message: string }>`: POST /auth/reset-password
      - `verifyEmail(data: VerifyEmailData): Promise<{ message: string }>`: POST /auth/verify-email
      - `resendVerification(): Promise<{ message: string }>`: POST /auth/resend-verification
      
      **Error Handling:** Let axios interceptor handle errors; API functions throw on error
      
      **Files:** `frontend/src/api/authApi.ts`
      
      **Verify:** Import API functions and confirm TypeScript types align with backend schemas; no compilation errors.

- [ ] 20. Update axios client to include credentials and handle 401
      
      **What:** Modify frontend/src/lib/api.ts to add `withCredentials: true` (for session cookies) and add response interceptor to redirect to /login on 401 Unauthorized.
      
      **Changes:**
      1. Add `withCredentials: true` to axios.create config
      2. Add response interceptor: on 401 status, redirect to `/login?redirect=${encodeURIComponent(window.location.pathname)}` (store intended destination for post-login redirect)
      
      **Files:** `frontend/src/lib/api.ts`
      
      **Verify:** Read lib/api.ts and confirm withCredentials is true; confirm interceptor checks error.response?.status === 401 and redirects.

---

### PRIORITY 6: Frontend Auth Context + Hook

- [ ] 21. Create AuthContext in `frontend/src/contexts/AuthContext.tsx`
      
      **What:** Implement React context for global authentication state with user, loading, and auth functions.
      
      **Context Interface:**
      ```typescript
      interface AuthContextType {
        user: User | null;
        loading: boolean;
        isAuthenticated: boolean;
        login: (data: LoginData) => Promise<void>;
        logout: () => Promise<void>;
        register: (data: RegisterData) => Promise<void>;
      }
      ```
      
      **AuthProvider Behavior:**
      - On mount: call getCurrentUser() to restore session from cookie, set user state, set loading=false
      - login: call authApi.login, update user state
      - logout: call authApi.logout, clear user state, redirect to /login
      - register: call authApi.register, do NOT set user state (user must verify email first), redirect to /verify-email with success message
      - isAuthenticated: computed as `user !== null`
      
      **Error Handling:** Catch API errors, display user-friendly error messages (use browser alert or toast for now; can be replaced with toast library later)
      
      **Files:** `frontend/src/contexts/AuthContext.tsx`
      
      **Verify:** Wrap a test component with AuthProvider, useAuth hook, and confirm user state updates on login/logout; confirm loading state prevents flash of unauthenticated content.

- [ ] 22. Create useAuth hook in `frontend/src/hooks/useAuth.ts`
      
      **What:** Simple hook to consume AuthContext with error handling if used outside provider.
      
      **Code:**
      ```typescript
      import { useContext } from 'react';
      import { AuthContext } from '../contexts/AuthContext';
      
      export function useAuth() {
        const context = useContext(AuthContext);
        if (!context) {
          throw new Error('useAuth must be used within AuthProvider');
        }
        return context;
      }
      ```
      
      **Files:** `frontend/src/hooks/useAuth.ts`
      
      **Verify:** Import useAuth in a component within AuthProvider and confirm it returns context; try using outside provider and confirm error is thrown.

---

### PRIORITY 7: Frontend Auth Pages

- [ ] 23. Create AuthLayout component in `frontend/src/components/AuthLayout.tsx`
      
      **What:** Two-panel layout for all auth pages: left panel with branding, right panel with form slot. Responsive: stacks vertically on mobile/tablet.
      
      **Left Panel Content:**
      - Logo placeholder or text "AI Orchestrator" in emerald (primary-400)
      - Heading: "Orchestrate AI. Simplify Work."
      - Supporting text: "Build, execute, and optimize intelligent workflows using multiple AI models through one unified workspace."
      - SVG illustration: Simple DAG visual (circles connected by lines) using emerald/primary colors, created inline with SVG or CSS
      
      **Right Panel:** Children slot for form content
      
      **Styling:** Use existing Tailwind theme (surface/primary colors), glass effect (backdrop-blur), dark background
      
      **Responsive:** On mobile (<768px), left panel shrinks to just logo + tagline, right panel full width
      
      **Files:** `frontend/src/components/AuthLayout.tsx`
      
      **Verify:** Render AuthLayout with sample form content and confirm two-panel layout appears correctly; test responsive behavior by resizing browser.

- [ ] 24. Create Login page in `frontend/src/pages/Login.tsx`
      
      **What:** Login form with email, password, remember me checkbox, forgot password link, sign in button with loading state.
      
      **Form Fields:**
      - Email input (type="email", required, autofocus)
      - Password input (type="password", required) with show/hide toggle (lucide-react Eye/EyeOff icons)
      - Remember me checkbox (optional)
      - Forgot password link (to /forgot-password)
      - Sign in button (primary emerald button, disabled during loading, shows spinner when loading)
      - Link to signup: "Don't have an account? Sign up"
      
      **Behavior:**
      - On mount: if already authenticated (via useAuth), redirect to /dashboard
      - On submit: call useAuth().login, on success redirect to stored redirect param or /dashboard, on error show error message below form
      - Client-side validation: email format, password not empty
      
      **Styling:** Use AuthLayout wrapper, emerald primary colors, dark surface theme, consistent with existing dashboard
      
      **Files:** `frontend/src/pages/Login.tsx`
      
      **Verify:** Navigate to /login, fill form, submit; confirm loading state appears, successful login redirects to dashboard, invalid credentials show error message.

- [ ] 25. Create Signup page in `frontend/src/pages/Signup.tsx`
      
      **What:** Registration form with full name, email, password, confirm password, terms checkbox, sign up button with loading state.
      
      **Form Fields:**
      - Full name input (required)
      - Email input (type="email", required)
      - Password input (type="password", required) with show/hide toggle
      - Confirm password input (type="password", required) with show/hide toggle
      - Password strength indicator (weak/medium/strong based on length and complexity)
      - Terms and Privacy Policy checkbox (required): "I agree to the Terms of Service and Privacy Policy"
      - Sign up button (disabled until form valid and terms accepted)
      - Link to login: "Already have an account? Sign in"
      
      **Validation:**
      - Email format and uniqueness (server-side error if duplicate)
      - Password minimum length from config (show requirement below password field)
      - Password strength: weak (< 8 chars), medium (8+ chars), strong (8+ chars + uppercase + number + symbol)
      - Passwords match
      - Terms accepted
      
      **Behavior:**
      - On submit: call useAuth().register, on success redirect to /verify-email with email in URL params, on error show error message (e.g., "Email already registered")
      
      **Styling:** Use AuthLayout wrapper, emerald colors, password strength indicator as colored bar (red/yellow/green)
      
      **Files:** `frontend/src/pages/Signup.tsx`
      
      **Verify:** Fill form with valid/invalid data and confirm validation messages appear; submit and confirm redirect to /verify-email on success, error message on duplicate email.

- [ ] 26. Create ForgotPassword page in `frontend/src/pages/ForgotPassword.tsx`
      
      **What:** Simple form with email input to request password reset link.
      
      **Form Fields:**
      - Email input (type="email", required, autofocus)
      - Submit button "Send Reset Link" (disabled during loading)
      - Back to login link
      
      **Behavior:**
      - On submit: call authApi.forgotPassword, always show success message (non-enumeration): "If an account exists for this email, password reset instructions have been sent. Please check your inbox."
      - After success: disable form, show success message, display "Return to login" button
      
      **Styling:** Use AuthLayout wrapper, centered content, simple and clean
      
      **Files:** `frontend/src/pages/ForgotPassword.tsx`
      
      **Verify:** Submit with any email and confirm non-enumeration message is displayed; confirm no network error leaks user existence.

- [ ] 27. Create ResetPassword page in `frontend/src/pages/ResetPassword.tsx`
      
      **What:** Form to set new password using token from URL query params.
      
      **URL Param:** Read token from `?token=` query param using useSearchParams from react-router-dom
      
      **Form Fields:**
      - New password input (type="password", required) with show/hide toggle
      - Confirm new password input (type="password", required) with show/hide toggle
      - Password strength indicator (same as signup)
      - Submit button "Reset Password" (disabled until valid)
      
      **Validation:** Password min length, passwords match, password strength indicator
      
      **Behavior:**
      - On mount: check token exists in URL, if not show error "Invalid or missing reset token"
      - On submit: call authApi.resetPassword with token and new_password, on success show success message and redirect to /login after 2 seconds, on error (expired/invalid token) show error message
      
      **Error Handling:** Expired token shows "Reset link has expired. Please request a new one." with link to /forgot-password
      
      **Styling:** Use AuthLayout wrapper
      
      **Files:** `frontend/src/pages/ResetPassword.tsx`
      
      **Verify:** Navigate to /reset-password?token=test123, fill form, submit; confirm success redirects to login, expired token shows appropriate error.

- [ ] 28. Create VerifyEmail page in `frontend/src/pages/VerifyEmail.tsx`
      
      **What:** Auto-verify email on mount if token in URL, otherwise show resend verification option.
      
      **URL Param:** Read token from `?token=` query param using useSearchParams
      
      **Behavior:**
      - On mount: if token exists, call authApi.verifyEmail(token), on success show success message "Email verified successfully! Redirecting to dashboard..." and redirect to /dashboard after 2 seconds, on error (expired/invalid) show error message
      - If no token (user navigated manually): show message "Please check your email for the verification link" and button "Resend Verification Email" (requires authentication via useAuth)
      - On resend: call authApi.resendVerification, show success message "Verification email sent"
      
      **UI States:**
      - Verifying (spinner)
      - Success (checkmark icon, success message, countdown to redirect)
      - Error (error icon, error message, resend button or link to /login)
      - No token (info message, resend button if authenticated, login link if not)
      
      **Styling:** Use AuthLayout wrapper, centered content with icons (lucide-react CheckCircle, XCircle, Mail)
      
      **Files:** `frontend/src/pages/VerifyEmail.tsx`
      
      **Verify:** Navigate with valid token and confirm auto-verification succeeds; navigate without token and confirm resend option appears; test expired token error handling.

- [ ] 29. Create ProtectedRoute component in `frontend/src/components/ProtectedRoute.tsx`
      
      **What:** Wrapper component that protects routes requiring authentication. Checks useAuth() state and redirects to /login if not authenticated.
      
      **Props:** `children: ReactNode`, optional `requireVerified?: boolean` (default false)
      
      **Behavior:**
      - While loading: show loading spinner (centered)
      - If not authenticated: redirect to `/login?redirect=${encodeURIComponent(location.pathname)}`
      - If requireVerified=true and user.is_email_verified=false: redirect to /verify-email with message
      - If authenticated (and verified if required): render children
      
      **Files:** `frontend/src/components/ProtectedRoute.tsx`
      
      **Verify:** Wrap a route with ProtectedRoute, navigate while logged out and confirm redirect to login with redirect param; login and confirm redirect to original destination.

---

### PRIORITY 8: Frontend Integration

- [ ] 30. Update App.tsx to integrate authentication
      
      **What:** Wrap app with AuthProvider, add auth routes, protect existing routes with ProtectedRoute.
      
      **Changes:**
      1. Import AuthProvider and wrap BrowserRouter contents
      2. Add public auth routes BEFORE Layout:
         - `/login` → Login
         - `/signup` → Signup
         - `/forgot-password` → ForgotPassword
         - `/reset-password` → ResetPassword
         - `/verify-email` → VerifyEmail
      3. Wrap existing Layout route with ProtectedRoute (so all dashboard/workflow routes require auth)
      4. Add redirect logic: if authenticated user navigates to /login or /signup, redirect to /dashboard
      
      **Route Structure:**
      ```tsx
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public auth routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            
            {/* Protected app routes */}
            <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
              {/* Existing routes unchanged */}
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
      ```
      
      **Files:** `frontend/src/App.tsx`
      
      **Verify:** Start frontend, navigate to / without login and confirm redirect to /login; login and confirm redirect to dashboard; navigate to /login while authenticated and confirm redirect to dashboard.

- [ ] 31. Update Layout.tsx to add user section in sidebar
      
      **What:** Add user section at the bottom of the sidebar with avatar (first letter of name), name, and dropdown menu with Profile, Settings, Logout options.
      
      **User Section Content:**
      - Avatar: circle with first letter of user.full_name in emerald background
      - Full name and email (truncated if long)
      - Dropdown menu (triggered by click on user section):
        - Profile (placeholder route for now)
        - Settings (placeholder route for now)
        - Divider
        - Logout (calls useAuth().logout())
      
      **Icons:** Use lucide-react User, Settings, LogOut icons
      
      **Styling:** Match existing sidebar style (dark surface, emerald accents), dropdown positioned above user section (bottom-anchored)
      
      **Position:** Below nav links, above footer, fixed to bottom of sidebar
      
      **Files:** `frontend/src/components/Layout.tsx`
      
      **Verify:** Login and navigate to dashboard; confirm user section appears in sidebar with correct name/email; click to open dropdown and confirm logout works.

---

### PRIORITY 9: Tests

- [ ] 32. Write backend unit tests for auth_service in `backend/tests/unit/test_auth_service.py`
      
      **What:** Test all auth_service functions in isolation with mocked database session.
      
      **Test Cases:**
      - `test_register_user_success`: Creates user with hashed password, email_normalized lowercase, is_email_verified=False
      - `test_register_user_duplicate_email`: Raises HTTPException 409 when email already exists (case-insensitive)
      - `test_authenticate_user_success`: Returns user when email and password match
      - `test_authenticate_user_wrong_password`: Returns None for invalid password
      - `test_authenticate_user_inactive`: Returns None for inactive user
      - `test_create_password_reset_token`: Creates token with correct expiry
      - `test_verify_reset_token_valid`: Returns user for valid token
      - `test_verify_reset_token_expired`: Returns None for expired token
      - `test_reset_password_success`: Updates password and marks token as used
      - `test_create_verification_token`: Creates verification token
      - `test_verify_email_success`: Sets is_email_verified=True and marks token as used
      - `test_verify_email_invalid_token`: Returns False for invalid token
      
      **Fixtures:** Use pytest fixtures for mocked AsyncSession, sample user data
      
      **Files:** `backend/tests/unit/test_auth_service.py`
      
      **Verify:** Run `python -m pytest backend/tests/unit/test_auth_service.py -c backend/pytest.ini --rootdir backend` and confirm all tests pass.

- [ ] 33. Write backend integration tests for auth API in `backend/tests/integration/test_auth_api.py`
      
      **What:** Test full authentication flows against test database using httpx AsyncClient.
      
      **Test Cases:**
      - `test_register_login_logout_flow`: Register user → login → GET /auth/me (with cookie) → logout → GET /auth/me (expect 401)
      - `test_register_duplicate_email`: Second registration with same email returns 409
      - `test_login_invalid_credentials`: Login with wrong password returns 401
      - `test_forgot_password_reset_flow`: Request reset → reset password with token → login with new password
      - `test_reset_password_expired_token`: Reset with expired token returns 400
      - `test_verify_email_valid_token`: Verify email with valid token, confirm user.is_email_verified=True
      - `test_verify_email_invalid_token`: Verify with invalid token returns 400
      - `test_protected_route_without_auth`: GET /auth/me without cookie returns 401
      - `test_rate_limiting`: Send 11 register requests and confirm 11th returns 429
      
      **Fixtures:** Use existing client, db_session fixtures from conftest.py; add helper fixture for creating test user
      
      **Files:** `backend/tests/integration/test_auth_api.py`
      
      **Verify:** Run `python -m pytest backend/tests/integration/test_auth_api.py -c backend/pytest.ini --rootdir backend` and confirm all tests pass.

- [ ] 34. Write frontend tests for Login component in `frontend/tests/auth/Login.test.tsx`
      
      **What:** Test Login component rendering, validation, and interaction using Vitest + React Testing Library.
      
      **Test Cases:**
      - `test_renders_login_form`: Confirms email, password inputs and submit button render
      - `test_email_validation`: Type invalid email and confirm error message
      - `test_password_visibility_toggle`: Click show/hide password icon and confirm input type changes
      - `test_login_success`: Fill form, submit, mock successful API call, confirm redirect to dashboard
      - `test_login_error`: Mock API error, submit form, confirm error message displays
      - `test_remember_me_checkbox`: Check remember me and confirm it's part of submitted data
      
      **Mocking:** Mock authApi.login using vi.mock, mock useAuth hook
      
      **Files:** `frontend/tests/auth/Login.test.tsx`
      
      **Verify:** Run `cd frontend && npm test -- Login.test.tsx` and confirm all tests pass.

- [ ] 35. Write frontend tests for Signup component in `frontend/tests/auth/Signup.test.tsx`
      
      **What:** Test Signup component validation and password strength indicator.
      
      **Test Cases:**
      - `test_renders_signup_form`: Confirms all inputs and submit button render
      - `test_password_mismatch`: Type different passwords in confirm field and confirm error message
      - `test_password_strength_indicator`: Type weak/medium/strong passwords and confirm indicator updates
      - `test_terms_acceptance_required`: Submit without checking terms and confirm validation error
      - `test_signup_success`: Fill form, submit, mock successful API call, confirm redirect to verify-email
      - `test_signup_duplicate_email`: Mock 409 error, confirm error message displays
      
      **Files:** `frontend/tests/auth/Signup.test.tsx`
      
      **Verify:** Run `cd frontend && npm test -- Signup.test.tsx` and confirm all tests pass.

- [ ] 36. Write frontend tests for AuthContext in `frontend/tests/auth/AuthContext.test.tsx`
      
      **What:** Test AuthContext state management and auth functions.
      
      **Test Cases:**
      - `test_initial_loading_state`: Confirm loading=true on mount
      - `test_loads_user_on_mount`: Mock getCurrentUser API call, confirm user state updates and loading=false
      - `test_login_updates_state`: Call login function, confirm user state updates
      - `test_logout_clears_state`: Call logout function, confirm user=null
      - `test_isAuthenticated_computed`: Confirm isAuthenticated is true when user exists, false when null
      
      **Mocking:** Mock authApi functions
      
      **Files:** `frontend/tests/auth/AuthContext.test.tsx`
      
      **Verify:** Run `cd frontend && npm test -- AuthContext.test.tsx` and confirm all tests pass.

---

### PRIORITY 10: Documentation

- [ ] 37. Create AUTH_SETUP.md documentation
      
      **What:** Comprehensive authentication setup guide for developers and deployers.
      
      **Sections:**
      1. **Overview**: Summary of authentication system (session-based, cookie httponly, email verification, password reset)
      2. **Environment Variables**: Table of all auth-related variables with descriptions and example values
      3. **Database Migration**: Commands to apply auth migrations (`cd backend && alembic upgrade head`)
      4. **SMTP Configuration**: 
         - Development mode (emails logged to console, no SMTP needed)
         - Production SMTP setup examples (Gmail, SendGrid, AWS SES)
         - Testing SMTP with Mailtrap
      5. **Password Requirements**: Configurable via PASSWORD_MIN_LENGTH, recommended 8+ with complexity
      6. **Session Management**: Cookie lifetime, refresh behavior, security settings (httponly, secure, samesite)
      7. **Email Verification**: Flow description, enable/disable via REQUIRE_EMAIL_VERIFICATION
      8. **Rate Limiting**: 10 requests/minute on auth endpoints, configurable via slowapi
      9. **Security Best Practices**: 
         - Use strong SESSION_SECRET_KEY in production (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
         - Enable HTTPS (secure cookies)
         - Configure CORS_ORIGINS appropriately
         - Regular session cleanup (expired sessions)
      10. **Testing**: Commands to run auth tests (unit + integration + frontend)
      11. **Troubleshooting**: Common issues (cookie not set, SMTP errors, 401 on protected routes)
      
      **Files:** `AUTH_SETUP.md` (project root)
      
      **Verify:** Read AUTH_SETUP.md and confirm all sections are complete, accurate, and follow existing documentation style from README.md.

- [ ] 38. Update README.md with authentication section
      
      **What:** Add brief authentication overview to README.md and link to AUTH_SETUP.md for details.
      
      **Changes:**
      1. In the "Features" section, add bullet point: "**Authentication** — secure session-based authentication with email verification, password reset, and protected routes. See [AUTH_SETUP.md](AUTH_SETUP.md) for configuration."
      2. In the "Architecture" diagram, add note that protected API routes require session cookie
      3. In the "Quick start" section, add note: "The default setup includes authentication. First user registered can access all features; multi-user support and roles are configured but role-based access control is not yet enforced."
      4. In the "Configuration" table, add row linking to AUTH_SETUP.md for auth variables
      
      **Files:** `README.md`
      
      **Verify:** Read README.md and confirm auth section is integrated naturally with existing content, no broken links.

---

## Verification Strategy

After completing all items:

1. **Backend Verification:**
   ```bash
   cd backend
   alembic upgrade head  # Apply migrations
   python -m pytest tests/unit/test_auth_service.py -c pytest.ini --rootdir backend
   python -m pytest tests/integration/test_auth_api.py -c pytest.ini --rootdir backend
   uvicorn backend.app.main:app --reload --port 8000
   # Navigate to http://localhost:8000/docs and test auth endpoints in Swagger UI
   ```

2. **Frontend Verification:**
   ```bash
   cd frontend
   npm install  # Install any new dependencies
   npm test  # Run all tests including new auth tests
   npm run dev  # Start dev server
   # Navigate to http://localhost:5173 and test full auth flows:
   # - Register new account
   # - Check console for verification email (dev mode)
   # - Verify email with token from console
   # - Login with credentials
   # - Access dashboard (protected route)
   # - Logout
   # - Test forgot password flow
   ```

3. **Integration Verification:**
   - Complete user journey: signup → verify email → login → access protected route → logout
   - Test all error cases: invalid credentials, expired tokens, duplicate emails
   - Verify session persistence: refresh page while logged in and confirm user stays logged in
   - Test rate limiting: rapid-fire auth requests trigger 429
   - Verify cookie security: inspect browser DevTools → Application → Cookies and confirm httponly, secure (in production), samesite flags

4. **Security Verification:**
   - Confirm passwords are hashed with Argon2 (check database)
   - Confirm session tokens are hashed with SHA-256 (check database)
   - Confirm password reset/email verification tokens are hashed (check database)
   - Confirm non-enumeration: forgot password returns same message for existing/non-existing emails
   - Confirm protected routes return 401 without valid session cookie
   - Confirm inactive users cannot login
   - Confirm unverified users are blocked if REQUIRE_EMAIL_VERIFICATION=true

---

## Implementation Notes

**Dependencies:** Complete each priority in order; later priorities depend on earlier ones. Within a priority, complete items in the listed order (e.g., models before migration, services before API endpoints).

**Code Patterns:** Strictly follow existing patterns from the codebase:
- Backend models: workflow.py, stage.py
- Backend schemas: workflow.py, stage.py (Pydantic v2 with Field, model_config)
- Backend API: workflows.py (router prefix, Depends(get_db), AsyncSession)
- Backend migrations: 001_initial_tables (exact syntax for columns, FKs, indexes)
- Frontend components: Layout.tsx (Tailwind classes, lucide-react icons)
- Frontend API: existing axios instance from lib/api.ts
- Tests: conftest.py fixtures, existing test patterns

**Theme Consistency:** All auth UI must match the existing dashboard design:
- Colors: emerald primary (#3ecf8e, #24b47e, #006239), dark surface (#1c1c1c, #2e2e2e)
- Typography: existing font stack from tailwind.config.js
- Spacing: consistent with existing pages (p-8, gap-4, etc.)
- Icons: lucide-react only (already in dependencies)

**Email Templates:** Keep HTML simple and inline styles for email client compatibility. Test with Mailtrap or similar service before production deployment.

**Error Handling:** User-facing error messages should be helpful but not leak sensitive information (e.g., don't reveal whether an email is registered except on duplicate registration).

**Rate Limiting:** slowapi integrates with FastAPI via middleware; apply @limiter decorators to auth endpoints.

**Session Cleanup:** Expired sessions accumulate in the database; implement periodic cleanup job (can be added as a follow-up task or manual `DELETE FROM sessions WHERE expires_at < NOW()` query).

**Multi-tenancy:** The `user_id` FK on workflows table enables per-user workflow isolation; enforcement in API endpoints (filter by current_user.id) is not included in this plan and should be a follow-up task.

**Role-Based Access Control:** User.role field is created but not enforced; RBAC implementation (admin-only routes, permissions) is not included in this plan and should be a follow-up task.

