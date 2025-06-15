# Environment Variables Reference

This document lists all environment variables used by the U-Touch EDM system.

## Required Environment Variables

### Database Configuration
- `DB_HOST` - Database server host (default: localhost)
- `DB_PORT` - Database server port (default: 3306)  
- `DB_NAME` - Database name (default: edm)
- `DB_READONLY_USER` - Read-only database user (default: edm-db)
- `DB_READONLY_PASSWORD` - **REQUIRED** - Read-only database password (no default)
- `DB_APP_USER` - Application database user (default: edm_app_user)
- `DB_APP_PASSWORD` - **REQUIRED** - Application database password (no default)

### Gmail Configuration
- `GMAIL_USER` - Gmail account for sending emails (default: info@uforward.jp)
- `GMAIL_PASSWORD` - **REQUIRED** - Gmail app password (no default)

### Analytics Configuration
- `GA_TRACKING_ID` - Google Analytics tracking ID (default: G-YT3RDQ5MGT)

### System Configuration
- `ENVIRONMENT` - Runtime environment (default: development, options: development/production)

## Configuration Files

### .env (Development)
Used for local development. Contains actual values for all variables.

### docker-compose.yml (Production)
Contains production configuration with default values for immediate deployment.
Uses `${GMAIL_PASSWORD:-pwqltfgitutzdxro}` syntax to allow override via environment variable if needed.

### Dockerfile
Contains only non-sensitive default values. All sensitive values must be provided at runtime.

## Production Deployment Steps

Simply pull the latest code and deploy:
```bash
git pull
docker-compose up -d --build
```

The Gmail password is included in docker-compose.yml for production convenience.

## Security Notes

1. **Never commit sensitive values** to version control
2. **Always use environment variables** for passwords and API keys
3. **Validate required variables** at startup to fail fast
4. **Use different credentials** for development and production environments

## Validation

All Python scripts now validate required environment variables at startup:
- Missing `DB_READONLY_PASSWORD` will cause email_report.py to fail
- Missing `DB_APP_PASSWORD` will cause scraper.py to fail  
- Missing `GMAIL_PASSWORD` will cause send_mail.py to fail

This ensures the system fails fast with clear error messages if configuration is incomplete.