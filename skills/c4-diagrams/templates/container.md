# Container Diagram (L2) - Mermaid Template

Shows the high-level technical building blocks (containers) within the system.

```mermaid
C4Container
    title Container Diagram - [System Name]

    Person(user, "User", "Description")

    System_Boundary(system, "System Name") {
        Container(web_app, "Web Application", "Flask", "Serves UI and API")
        Container(api, "API Gateway", "Flask", "Handles requests")
        Container(worker, "Background Worker", "Celery", "Async processing")
        ContainerDb(db, "Database", "PostgreSQL", "Stores data")
        ContainerDb(cache, "Cache", "Redis", "Session and cache")
    }

    System_Ext(ext_auth, "Auth Provider", "Authentication")
    System_Ext(ext_api, "External API", "Data source")

    Rel(user, web_app, "Uses", "HTTPS")
    Rel(web_app, api, "Calls", "HTTP")
    Rel(api, db, "Reads/Writes", "SQL")
    Rel(api, cache, "Caches", "Redis protocol")
    Rel(api, ext_auth, "Authenticates", "OAuth")
    Rel(worker, ext_api, "Fetches", "HTTPS")
```

## Elements

| Element | Usage |
|---------|-------|
| `System_Boundary(id, "Name")` | Groups containers |
| `Container(id, "Name", "Tech", "Desc")` | Application/service |
| `ContainerDb(id, "Name", "Tech", "Desc")` | Database |
| `ContainerQueue(id, "Name", "Tech", "Desc")` | Message queue |
| `Rel(from, to, "Label", "Tech")` | Relationship |
