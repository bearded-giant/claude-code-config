# 2FA Login Process Architecture

## Context Diagram (L1)

```mermaid
C4Context
    title System Context - Two-Factor Authentication

    Person(merchant, "Merchant", "User logging into dashboard")

    System(dashboard, "Merchant Dashboard", "Web application with 2FA login")

    System_Ext(auth0, "Auth0", "Primary identity provider")
    System_Ext(twilio, "Twilio", "SMS delivery for OTP codes")
    System_Ext(email_provider, "Email Service", "Email delivery for OTP codes")

    Rel(merchant, dashboard, "Logs in with credentials + OTP")
    Rel(dashboard, auth0, "Validates primary credentials")
    Rel(dashboard, twilio, "Sends SMS OTP")
    Rel(dashboard, email_provider, "Sends email OTP")
```

Merchants authenticate via the dashboard, which validates primary credentials through Auth0 and delivers one-time passwords via SMS or email.

## Container Diagram (L2)

```mermaid
C4Container
    title Container Diagram - Two-Factor Authentication

    Person(merchant, "Merchant", "Dashboard user")

    System_Boundary(dashboard, "Merchant Dashboard") {
        Container(web, "Web App", "Flask", "Login UI and session management")
        Container(api, "Auth API", "Flask Blueprint", "Authentication endpoints")
        Container(otp_service, "OTP Service", "Python", "Generates and validates OTPs")
        ContainerDb(db, "Database", "PostgreSQL", "User 2FA settings, OTP records")
        ContainerDb(cache, "Cache", "Redis", "Rate limiting, OTP temp storage")
    }

    System_Ext(auth0, "Auth0", "Identity provider")
    System_Ext(twilio, "Twilio", "SMS gateway")

    Rel(merchant, web, "Submits credentials", "HTTPS")
    Rel(web, api, "POST /auth/login", "HTTP")
    Rel(api, auth0, "Validates password", "OAuth")
    Rel(api, otp_service, "Requests OTP")
    Rel(otp_service, db, "Stores OTP hash")
    Rel(otp_service, cache, "Rate limit check")
    Rel(otp_service, twilio, "Sends SMS", "HTTPS")
    Rel(merchant, web, "Submits OTP", "HTTPS")
    Rel(api, otp_service, "Validates OTP")
```

Login flow: web app calls auth API, which validates credentials via Auth0, then triggers OTP generation and delivery. OTP validation completes the 2FA flow.
