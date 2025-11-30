```mermaid
erDiagram
    polymorphic_parents ||--o{ entities : inherits
    polymorphic_parents ||--o{ locations : inherits
    polymorphic_parents ||--|{ attributes : has_attribute

    entities ||--|{ positions : reports
    
    routes ||--|{ locations : starts_at
    routes ||--|{ locations : ends_at
    
    polymorphic_parents {
        uuid id PK
        enum type
    }
    attributes {
        integer id PK
        uuid parent_id FK
        string(100) key
        string(255) value
        enum value_type
    }
    entities {
        uuid id PK,FK "References polymorphic_parents"
        string(100) name
        enum type
        string(255) image
        string(500) description
    }
    locations {
        uuid id PK,FK "References polymorphic_parents"
        geometry geom "PostGIS POINT (4326)"
        string(100) name
        enum type
    }
    positions {
        integer id PK
        uuid entity_id FK
        geometry geom "PostGIS POINT (4326)"
        datetime timestamp
    }
    routes {
        uuid id PK
        uuid start_id FK
        uuid end_id FK
    }

```