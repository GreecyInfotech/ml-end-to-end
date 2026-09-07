# ML Gateway Architecture and API Orchestration

## 1. Request Flow

```text
Client
  -> ML Gateway :8080
     -> API key authentication and role authorization
       -> request ID propagation
       -> rate limiting
     -> timeout and bounded transient retries
     -> fallback/error boundary
       -> model API :8000
            -> champion alias/fallback
            -> feature contract check
            -> prediction
```

The gateway is intentionally separate from model serving. It handles edge concerns while the API owns feature engineering, model loading, and prediction behavior.

## 2. Gateway Endpoints

| Endpoint | Behavior |
|---|---|
| `/health` | Gateway process health without requiring model availability |
| `/ready` | Verifies gateway and model backend readiness |
| `/metrics` | Prometheus gateway metrics |
| `/metrics.json` | Gateway request, error, rate-limit, retry, and fallback counters |
| `/predict` | Validates edge access and proxies JSON prediction requests |

The gateway adds or preserves `X-Request-ID` and forwards it to the model API.

## 3. Production Controls

Environment variables:

```text
MODEL_API_URL
GATEWAY_API_KEY
GATEWAY_API_KEYS                 # JSON map: {"key":"role"}
GATEWAY_REQUIRED_ROLE            # readonly, predictor, or admin
GATEWAY_TIMEOUT_SECONDS
GATEWAY_BACKEND_MAX_RETRIES
GATEWAY_RETRY_BACKOFF_SECONDS
GATEWAY_RATE_LIMIT
GATEWAY_RATE_WINDOW_SECONDS
```

Authentication returns `401` for an unknown key. Authorization returns `403` when a known key's role is below `GATEWAY_REQUIRED_ROLE`. A single `GATEWAY_API_KEY` is treated as an admin key for backward compatibility; production deployments should prefer secret-managed `GATEWAY_API_KEYS` or provider-native OAuth/OIDC claims.

Transient backend failures (`502`, `503`, `504`, timeouts, and connection failures) receive bounded exponential retries. The gateway returns a controlled `503` fallback when all attempts fail and increments retry/fallback counters. Keep prediction handlers idempotent before increasing retry counts.

## 4. Local Run

```powershell
docker compose up -d api gateway
```

Gateway URL: `http://127.0.0.1:8080`

```powershell
$payload = @{arrival_hour=8; cargo_volume=1200.0; berth_wait_minutes=45.0; port_congestion="high"; weather="rain"; previous_delay_hours=1.5; crane_available=1} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8080/predict -Method Post -ContentType "application/json" -Body $payload
```

## 5. Cloud Mapping

| Gateway role | Azure | AWS | GCP |
|---|---|---|---|
| Edge gateway | API Management or Front Door + APIM | API Gateway or ALB + WAF | API Gateway or Cloud Load Balancing |
| Gateway container | Container Apps | ECS/Fargate | Cloud Run |
| Model API | Private Container App | Private ECS service | Internal Cloud Run service |
| Identity | Entra ID / managed identity | IAM/task roles | service accounts/IAM |

The gateway should be public only when protected by TLS, authentication, WAF/rate controls, and centralized logs. Keep the model API private behind the gateway.