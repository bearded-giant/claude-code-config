# Component Diagram (L3) - Mermaid Template

**Only generate when explicitly requested.** Shows internal components within a container.

```mermaid
C4Component
    title Component Diagram - [Container Name]

    Container_Boundary(api, "API Container") {
        Component(auth, "Auth Controller", "Flask Blueprint", "Handles authentication")
        Component(merchant, "Merchant Controller", "Flask Blueprint", "Merchant operations")
        Component(auth_service, "Auth Service", "Python", "Authentication logic")
        Component(merchant_service, "Merchant Service", "Python", "Business logic")
        Component(repo, "Repository", "SQLAlchemy", "Data access")
    }

    ContainerDb(db, "Database", "PostgreSQL", "Data storage")
    System_Ext(auth0, "Auth0", "Identity provider")

    Rel(auth, auth_service, "Uses")
    Rel(merchant, merchant_service, "Uses")
    Rel(auth_service, auth0, "Validates tokens")
    Rel(auth_service, repo, "Queries")
    Rel(merchant_service, repo, "Queries")
    Rel(repo, db, "Reads/Writes")
```

## Elements

| Element | Usage |
|---------|-------|
| `Container_Boundary(id, "Name")` | The container being detailed |
| `Component(id, "Name", "Tech", "Desc")` | Internal component |
| `Rel(from, to, "Label")` | Dependency/call |
