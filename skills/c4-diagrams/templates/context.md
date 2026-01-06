# Context Diagram (L1) - Mermaid Template

Shows the system in scope and its relationships with external actors and systems.

```mermaid
C4Context
    title System Context Diagram - [System Name]

    Person(user, "User", "Description of user role")
    Person(admin, "Admin", "Description of admin role")

    System(system, "System Name", "Brief system description")

    System_Ext(ext_system, "External System", "What it provides")
    System_Ext(ext_api, "External API", "What it provides")

    Rel(user, system, "Uses")
    Rel(admin, system, "Manages")
    Rel(system, ext_system, "Calls", "protocol")
    Rel(system, ext_api, "Fetches data from")
```

## Elements

| Element | Usage |
|---------|-------|
| `Person(id, "Name", "Desc")` | Human actors |
| `System(id, "Name", "Desc")` | System in scope |
| `System_Ext(id, "Name", "Desc")` | External systems |
| `Rel(from, to, "Label")` | Relationships |
| `Rel(from, to, "Label", "Tech")` | Relationship with technology |
