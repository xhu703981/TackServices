# TaskManagement Database Schema

---

## Table of Contents

- [Overview](#overview)
- [Structure](#structure)
- [Setup: extensions and shared trigger](#setup-extensions-and-shared-trigger)
- [Database Tables](#database-tables)
  - [Table: users](#table-users)
  - [Table: workspaces](#table-workspaces)
  - [Table: workspace_members](#table-workspace_members)
  - [Table: teams](#table-teams)
  - [Table: sprints](#table-sprints)
  - [Table: projects](#table-projects)
  - [Table: issues](#table-issues)
  - [Table: comments](#table-comments)
  - [Table: issue_activities](#table-issue_activities)
  - [Table: attachments](#table-attachments)
  - [Table: views](#table-views)
  - [Table: notifications](#table-notifications)
- [Key Relationships](#key-relationships)
- [Notes on Implementation](#notes-on-implementation)

---

## Overview

This schema defines the backend structure for TaskManagement, an issue tracker. It is optimized for high-performance PostgreSQL operations, utilizing pgvector for AI search and supporting a microservices-style event architecture with Kafka.

All timestamps are `TIMESTAMPTZ` (stored in UTC, converted on read), so times stay correct for users in different time zones.

---

## Structure

```
User
 ├── Workspace                      (workspaces, through workspace_members)
 │    ├── Members                   (workspace_members: Admin | Member)
 │    └── Teams                     (teams: key "ENG" → issues ENG-1, ENG-2, ...)
 │         ├── Issues               (issues)
 │         │    ├── Comments        (comments)
 │         │    ├── Activities      (issue_activities)
 │         │    └── Attachments     (attachments)
 │         ├── Cycles / Sprints     (sprints)
 │         ├── Projects             (projects: the features / epics that issues belong to)
 │         └── Views                (views: saved filters)
 └── Notifications                  (notifications)
```

- A user logs in once and can belong to several workspaces. Everything except the user's own account and notifications lives inside exactly one workspace.
- Every workspace member can work in every team of that workspace. Permissions come from the workspace role.
- A project is the parent of issues (`issues.project_id`). It replaces the old epic issue type.

---

## Setup: extensions and shared trigger

Two extensions must exist before the tables are created, and the `update_*_modtime` triggers below all call one shared function.

```sql
CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector: VECTOR type + hnsw index (needs the pgvector/pgvector:pg16 image)
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- trigram index for fuzzy name search (gin_trgm_ops)

CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## Database Tables

### Table: users

The account itself. It belongs to no workspace; roles live in `workspace_members`. Login is Google-only, so there is no password.

| Column           | Type      | Constraints      | Description                                                        |
| ---------------- | --------- | ---------------- | ------------------------------------------------------------------ |
| id               | SERIAL    | PRIMARY KEY      | Unique identifier for each user                                    |
| username         | TEXT      | UNIQUE, NOT NULL | User's chosen username                                             |
| email            | TEXT      | UNIQUE, NOT NULL | User's email address                                               |
| name             | TEXT      | NOT NULL         | Display name ("Keya Wang")                                         |
| auth_provider    | TEXT      |                  | "google"; NULL = made before Google login, linked by email on its first Google sign-in |
| auth_provider_id | TEXT      |                  | Google's user ID (the ID token's `sub`)                            |
| created_at       | TIMESTAMPTZ | NOT NULL         | When the user was created                                          |
| updated_at       | TIMESTAMPTZ | NOT NULL         | When the user was last updated                                     |

**Indexes:**

- PRIMARY KEY on `id` (automatically created)
- UNIQUE INDEX on `username` (automatically created by UNIQUE constraint)
- UNIQUE INDEX on `email` (automatically created by UNIQUE constraint)
- UNIQUE INDEX on `(auth_provider, auth_provider_id)` for OAuth lookups: one Google account maps to exactly one user

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    auth_provider TEXT, -- 'google'; NULL until an older account is linked
    auth_provider_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_auth ON users (auth_provider, auth_provider_id);

CREATE TRIGGER update_users_modtime BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: workspaces

The top-level container (one company or organization).

| Column     | Type        | Constraints      | Description                                          |
| ---------- | ----------- | ---------------- | ---------------------------------------------------- |
| id         | SERIAL      | PRIMARY KEY      | Unique workspace ID                                  |
| name       | TEXT        | NOT NULL         | Display name ("Acme Inc")                            |
| slug       | TEXT        | UNIQUE, NOT NULL | URL key: `/w/acme/...`; lowercase letters, digits, dashes |
| created_at | TIMESTAMPTZ | NOT NULL         | When the workspace was created                       |
| updated_at | TIMESTAMPTZ | NOT NULL         | Last settings change                                 |

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE INDEX on `slug` (every request finds its workspace by slug)

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS workspaces (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9][a-z0-9-]{2,31}$'), -- 3-32 chars
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER update_workspaces_modtime BEFORE UPDATE ON workspaces
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: workspace_members

Which users belong to which workspace, and their role there.

| Column       | Type        | Constraints                   | Description                                          |
| ------------ | ----------- | ----------------------------- | ---------------------------------------------------- |
| workspace_id | INTEGER     | PK, REFERENCES workspaces(id) | The workspace                                        |
| user_id      | INTEGER     | PK, REFERENCES users(id)      | The member                                           |
| role         | TEXT        | NOT NULL, DEFAULT 'Member'    | Admin (manages members, teams, settings) or Member   |
| joined_at    | TIMESTAMPTZ | NOT NULL                      | When the user joined                                 |

**Indexes:**

- PRIMARY KEY on `(workspace_id, user_id)`: also serves "members of a workspace" (leading column)
- INDEX on `user_id`: "workspaces I belong to", for the workspace switcher

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'Member' CHECK (role IN ('Admin', 'Member')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members (user_id);
```

---

### Table: teams

A group inside a workspace that owns issues, sprints, projects and views. Its key prefixes every issue key.

| Column            | Type        | Constraints                        | Description                             |
| ----------------- | ----------- | ---------------------------------- | --------------------------------------- |
| id                | SERIAL      | PRIMARY KEY                        | Unique team ID                          |
| workspace_id      | INTEGER     | NOT NULL, REFERENCES workspaces(id) | The workspace the team belongs to       |
| name              | TEXT        | NOT NULL                           | Team display name ("Engineering")       |
| key               | TEXT        | NOT NULL, UNIQUE with workspace_id | Issue key prefix ("ENG"); can't change after creation |
| description       | TEXT        | NOT NULL, DEFAULT ''               | What the team works on                  |
| last_issue_number | INTEGER     | NOT NULL, DEFAULT 0                | Last issue number handed out; the next issue is KEY-(last_issue_number+1). Not the number of issues: deleting ENG-3 does not lower it |
| is_archived       | BOOLEAN     | NOT NULL, DEFAULT FALSE            | Flag for active/archived status         |
| created_at        | TIMESTAMPTZ | NOT NULL                           | Date of team creation                   |
| updated_at        | TIMESTAMPTZ | NOT NULL                           | Last configuration change               |

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE INDEX on `(workspace_id, key)`: two workspaces can both have an "ENG" team. Its leading column also serves "teams of a workspace".
- GIN INDEX on `name` using pg_trgm

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    key TEXT NOT NULL CHECK (key ~ '^[A-Z][A-Z0-9]{1,9}$'), -- 2-10 chars, starts with a letter
    description TEXT NOT NULL DEFAULT '',
    last_issue_number INTEGER NOT NULL DEFAULT 0,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workspace_id, key)
);

CREATE INDEX IF NOT EXISTS idx_teams_name_search ON teams USING gin (name gin_trgm_ops);

CREATE TRIGGER update_teams_modtime BEFORE UPDATE ON teams
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: sprints

A team's time-boxed cycle of work.

| Column         | Type        | Constraints                    | Description                    |
| -------------- | ----------- | ------------------------------ | ------------------------------ |
| id             | SERIAL      | PRIMARY KEY                    | Unique sprint identifier       |
| team_id        | INTEGER     | NOT NULL, REFERENCES teams(id) | Team the sprint belongs to     |
| name           | TEXT        | NOT NULL                       | Sprint name (e.g., "Sprint 1") |
| goal           | TEXT        | NULL                           | Sprint goal/objective          |
| start_date     | TIMESTAMPTZ | NULL                           | Sprint start date              |
| end_date       | TIMESTAMPTZ | NULL                           | Sprint end date                |
| completed_date | TIMESTAMPTZ | NULL                           | Date sprint was completed      |
| status         | TEXT        | NOT NULL                       | planned, active, completed     |
| created_by     | INTEGER     | REFERENCES users(id)           | User who created the sprint    |
| created_at     | TIMESTAMPTZ | DEFAULT NOW()                  | Creation timestamp             |
| updated_at     | TIMESTAMPTZ | DEFAULT NOW()                  | Last update timestamp          |

**Indexes:**

- PRIMARY KEY on `id`
- INDEX on `(team_id, status)`: "active / planned sprints of a team". Its leading column also covers plain `team_id` lookups, so a separate `team_id` index isn't needed.
- INDEX on `(team_id, start_date)`: sprints of a team in date order
- UNIQUE PARTIAL INDEX on `team_id WHERE status = 'active'`: at most one active sprint per team

**SQL for creating the table:**

```sql
CREATE TABLE sprints (
    id SERIAL PRIMARY KEY,

    team_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    goal TEXT,

    start_date TIMESTAMPTZ NULL,
    end_date TIMESTAMPTZ NULL,
    completed_date TIMESTAMPTZ NULL,

    status TEXT NOT NULL DEFAULT 'planned',

    created_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_sprints_team
        FOREIGN KEY (team_id)
        REFERENCES teams(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_sprints_created_by
        FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE SET NULL,

    CONSTRAINT chk_sprints_status
        CHECK (status IN ('planned', 'active', 'completed')),

    CONSTRAINT chk_sprints_dates
        CHECK (end_date IS NULL OR start_date IS NULL OR end_date > start_date)
);

CREATE INDEX IF NOT EXISTS idx_sprints_team_status ON sprints (team_id, status);
CREATE INDEX IF NOT EXISTS idx_sprints_team_start ON sprints (team_id, start_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sprints_one_active ON sprints (team_id) WHERE status = 'active';

CREATE TRIGGER update_sprints_modtime BEFORE UPDATE ON sprints
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: projects

A feature or epic inside a team: the parent that groups related issues ("Dark mode", "Billing v2").

| Column      | Type        | Constraints                    | Description                                  |
| ----------- | ----------- | ------------------------------ | -------------------------------------------- |
| id          | SERIAL      | PRIMARY KEY                    | Unique project ID                            |
| team_id     | INTEGER     | NOT NULL, REFERENCES teams(id) | Team that owns the project                   |
| name        | TEXT        | NOT NULL                       | Project name                                 |
| description | TEXT        | NOT NULL, DEFAULT ''           | What the feature is                          |
| status      | TEXT        | NOT NULL, DEFAULT 'planned'    | planned, in_progress, paused, completed, canceled |
| lead_id     | INTEGER     | REFERENCES users(id)           | Person responsible for the project           |
| start_date  | DATE        |                                | Planned start                                |
| target_date | DATE        |                                | Planned finish                               |
| created_at  | TIMESTAMPTZ | NOT NULL                       | Creation timestamp                           |
| updated_at  | TIMESTAMPTZ | NOT NULL                       | Last update timestamp                        |

**Indexes:**

- PRIMARY KEY on `id`
- INDEX on `team_id`: projects of a team
- INDEX on `lead_id`: "projects I lead", and the `ON DELETE SET NULL` when a user is deleted

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'in_progress', 'paused', 'completed', 'canceled')),
    lead_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    start_date DATE,
    target_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (target_date IS NULL OR start_date IS NULL OR target_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_projects_team ON projects (team_id);
CREATE INDEX IF NOT EXISTS idx_projects_lead ON projects (lead_id);

CREATE TRIGGER update_projects_modtime BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: issues

| Column       | Type         | Constraints                    | Description               |
| ------------ | ------------ | ------------------------------ | ------------------------- |
| id           | SERIAL       | PRIMARY KEY                    | Internal unique ID        |
| team_id      | INTEGER      | NOT NULL, REFERENCES teams(id) | Team that owns the issue  |
| number       | INTEGER      | NOT NULL, UNIQUE with team_id  | The 12 in ENG-12. The key "ENG-12" is team key + number, so it isn't stored |
| issue_type   | TEXT         | NOT NULL, DEFAULT 'task'       | task, bug, story          |
| project_id   | INTEGER      | REFERENCES projects(id)        | The project (feature) this issue belongs to; NULL = none |
| sprint_id    | INTEGER      | REFERENCES sprints(id)         | Sprint it's planned in; NULL = backlog |
| title        | TEXT         | NOT NULL                       | Issue headline            |
| description  | TEXT         |                                | Detailed task information |
| status       | TEXT         | NOT NULL, DEFAULT 'todo'       | todo, in_progress, in_review, done. "Backlog" is not a status: it means sprint_id IS NULL |
| priority     | SMALLINT     | NOT NULL, DEFAULT 3            | 1 Highest, 2 High, 3 Medium, 4 Low, 5 Lowest (sorts correctly with ORDER BY) |
| assignee_id  | INTEGER      | REFERENCES users(id)           | Assigned user             |
| reporter_id  | INTEGER      | REFERENCES users(id)           | Issue creator             |
| story_points | INTEGER      | DEFAULT 0                      | Estimated effort          |
| labels       | TEXT[]       | NOT NULL, DEFAULT '{}', at most 5 | Free-text tags ("frontend", "bug-bash") |
| due_date     | TIMESTAMPTZ  |                                | Deadline                  |
| embedding    | VECTOR(1536) |                                | Title+description embedding for semantic search |
| created_at   | TIMESTAMPTZ  | NOT NULL                       | Creation timestamp        |
| updated_at   | TIMESTAMPTZ  | NOT NULL                       | Last activity timestamp   |

**Indexes:**

- UNIQUE on `(team_id, number)`: finds "ENG-12" (look up team ENG in the workspace, then number 12). Its leading column also serves every "issues of a team" lookup.
- INDEX on `assignee_id`
- INDEX on `sprint_id` (sprint board, and the `ON DELETE SET NULL` when a sprint is deleted)
- INDEX on `project_id` (issues of a project, and the `ON DELETE SET NULL` when a project is deleted)
- HNSW INDEX on `embedding` for AI search

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    issue_type TEXT NOT NULL DEFAULT 'task' CHECK (issue_type IN ('task', 'bug', 'story')),
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL, -- deleting a project keeps its issues
    sprint_id INTEGER REFERENCES sprints(id) ON DELETE SET NULL, -- deleting a sprint sends its issues back to the backlog
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'in_review', 'done')),
    priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5), -- 1 Highest ... 5 Lowest
    assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reporter_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    story_points INTEGER NOT NULL DEFAULT 0 CHECK (story_points >= 0),
    labels TEXT[] NOT NULL DEFAULT '{}' CHECK (cardinality(labels) <= 5),
    due_date TIMESTAMPTZ,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (team_id, number)
);

CREATE INDEX IF NOT EXISTS idx_issues_assignee ON issues (assignee_id);
CREATE INDEX IF NOT EXISTS idx_issues_sprint ON issues (sprint_id);
CREATE INDEX IF NOT EXISTS idx_issues_project ON issues (project_id);
CREATE INDEX IF NOT EXISTS idx_issues_embedding ON issues USING hnsw (embedding vector_cosine_ops);

CREATE TRIGGER update_issues_modtime BEFORE UPDATE ON issues
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: comments

| Column     | Type      | Constraints                     | Description                       |
| ---------- | --------- | ------------------------------- | --------------------------------- |
| id         | SERIAL    | PRIMARY KEY                     | Unique identifier for the comment |
| issue_id   | INTEGER   | NOT NULL, REFERENCES issues(id) | Parent issue                      |
| author_id  | INTEGER   | REFERENCES users(id)            | User who wrote the comment        |
| parent_id  | INTEGER   | REFERENCES comments(id)         | Parent comment for threading      |
| content    | TEXT      | NOT NULL                        | Comment body                      |
| is_edited  | BOOLEAN   | DEFAULT FALSE                   | Shows edited state in UI          |
| created_at | TIMESTAMPTZ | NOT NULL                        | Creation timestamp                |
| updated_at | TIMESTAMPTZ | NOT NULL                        | Last modification timestamp       |

**Indexes:**

INDEX on issue_id (To load all comments for one ticket instantly)

INDEX on author_id (To find all comments by a specific user)

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    parent_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_edited BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_comments_issue ON comments (issue_id);
CREATE INDEX IF NOT EXISTS idx_comments_author ON comments (author_id);

CREATE TRIGGER update_comments_modtime BEFORE UPDATE ON comments
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: issue_activities

The history of an issue: one row per change ("Keya changed status from To Do to In Progress"). Rows are only ever inserted, never updated, so there is no `updated_at`.

| Column     | Type        | Constraints                     | Description                                           |
| ---------- | ----------- | ------------------------------- | ----------------------------------------------------- |
| id         | BIGSERIAL   | PRIMARY KEY                     | Unique activity ID (BIGSERIAL: this table grows fastest) |
| issue_id   | INTEGER     | NOT NULL, REFERENCES issues(id) | The issue that changed                                |
| actor_id   | INTEGER     | REFERENCES users(id)            | Who made the change                                   |
| action     | TEXT        | NOT NULL                        | created, updated                                      |
| field      | TEXT        |                                 | Changed column for `updated` ("status", "assignee_id"); NULL for `created` |
| old_value  | JSONB       |                                 | Value before the change                               |
| new_value  | JSONB       |                                 | Value after the change                                |
| created_at | TIMESTAMPTZ | NOT NULL                        | When it happened                                      |

**Indexes:**

- INDEX on `(issue_id, created_at)`: an issue's history in time order, without a separate sort

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS issue_activities (
    id BIGSERIAL PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (action IN ('created', 'updated')),
    field TEXT,
    old_value JSONB, -- JSONB so one column can hold a status string, a user id or a labels array
    new_value JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((action = 'updated') = (field IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_issue_activities_issue ON issue_activities (issue_id, created_at);
```

---

### Table: attachments

| Column       | Type      | Constraints                     | Description                             |
| ------------ | --------- | ------------------------------- | --------------------------------------- |
| id           | UUID      | PRIMARY KEY                     | Unique ID (usually matches S3 file key) |
| issue_id     | INTEGER   | NOT NULL, REFERENCES issues(id) | The issue this file belongs to          |
| uploader_id  | INTEGER   | REFERENCES users(id)            | The user who uploaded the file          |
| file_name    | TEXT      | NOT NULL                        | Original filename                       |
| file_url     | TEXT      | NOT NULL                        | Public/Private URL to cloud storage     |
| file_size    | BIGINT    | NOT NULL                        | Size in bytes                           |
| content_type | TEXT      | NOT NULL                        | MIME type (e.g., image/png)             |
| created_at   | TIMESTAMPTZ | NOT NULL, DEFAULT now()         | Date of upload                          |

**Indexes:**

- INDEX on issue_id (To list all files on a ticket)

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    uploader_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    content_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attachments_issue ON attachments (issue_id);
```

---

### Table: views

A saved filter over a team's issues ("My open bugs", "High priority this sprint").

| Column     | Type        | Constraints                    | Description                                  |
| ---------- | ----------- | ------------------------------ | -------------------------------------------- |
| id         | SERIAL      | PRIMARY KEY                    | Unique view ID                               |
| team_id    | INTEGER     | NOT NULL, REFERENCES teams(id) | Team whose issues the view shows             |
| owner_id   | INTEGER     | NOT NULL, REFERENCES users(id) | Who created the view                         |
| name       | TEXT        | NOT NULL                       | View name                                    |
| filters    | JSONB       | NOT NULL, DEFAULT '{}'         | The saved filter, e.g. `{"status": ["todo", "in_progress"], "priority": [1, 2], "assignee_id": [7], "labels": ["frontend"]}`; keys match the issue list's query parameters |
| is_shared  | BOOLEAN     | NOT NULL, DEFAULT FALSE        | FALSE: only the owner sees it. TRUE: everyone in the workspace |
| created_at | TIMESTAMPTZ | NOT NULL                       | Creation timestamp                           |
| updated_at | TIMESTAMPTZ | NOT NULL                       | Last update timestamp                        |

**Indexes:**

- INDEX on `team_id`: views of a team
- INDEX on `owner_id`: "my views", and the `ON DELETE CASCADE` when a user is deleted

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS views (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}',
    is_shared BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_views_team ON views (team_id);
CREATE INDEX IF NOT EXISTS idx_views_owner ON views (owner_id);

CREATE TRIGGER update_views_modtime BEFORE UPDATE ON views
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: notifications

| Column     | Type      | Constraints                    | Description                            |
| ---------- | --------- | ------------------------------ | -------------------------------------- |
| id         | SERIAL    | PRIMARY KEY                    | Unique notification ID                 |
| user_id    | INTEGER   | NOT NULL, REFERENCES users(id) | Recipient of the notification          |
| message    | TEXT      | NOT NULL                       | Notification body text                 |
| link       | TEXT      |                                | Redirect path including the workspace (e.g., "/w/acme/issue/ENG-101") |
| is_read    | BOOLEAN   | DEFAULT FALSE                  | Status for unread badges               |
| created_at | TIMESTAMPTZ | DEFAULT now()                  | When the alert was triggered           |

**Indexes:**

- PRIMARY KEY on `id`
- INDEX on `user_id`
- PARTIAL INDEX on unread notifications (`is_read = FALSE`)

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    link TEXT, -- Deep link to issue or comment
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notifications_user
ON notifications(user_id);

CREATE INDEX IF NOT EXISTS idx_unread_notifications_user
ON notifications(user_id)
WHERE is_read = FALSE;
```

---

## Key Relationships

**Relationship 1: User-to-Workspace (Membership)**

- Type: Many-to-Many
- Description: A user can belong to several workspaces, and has one role (Admin or Member) in each.
- Implementation: Through the `workspace_members` join table.
- Creation requirement: Whoever creates a workspace becomes its first Admin. A workspace must always keep at least one Admin (enforced at application level).
- Deletion behavior: Deleting a user or a workspace removes the membership rows (ON DELETE CASCADE). Removing a user from a workspace does not delete their historical contributions (comments, past assignments).

**Relationship 2: Workspace-to-Team**

- Type: One-to-Many
- Description: A workspace is divided into teams, each with its own issue key prefix.
- Implementation: Through the `workspace_id` foreign key in the teams table.
- Deletion behavior: Deleting a workspace deletes its teams, and through them everything inside (ON DELETE CASCADE).

**Relationship 3: Team-to-Issue**

- Type: One-to-Many
- Description: A team acts as a container for its issues, tasks, and bugs.
- Implementation: Through the `team_id` foreign key in the issues table.
- Creation requirement: Issues must be associated with a valid team to get a number (and so a key such as "ENG-12").
- Deletion behavior: When a team is deleted, all associated issues are permanently removed (ON DELETE CASCADE).

**Relationship 4: Team-to-Sprint**

- Type: One-to-Many
- Description: A team plans its work in time-boxed sprints (cycles).
- Implementation: Through the `team_id` foreign key in the sprints table.
- Deletion behavior: Deleting a team deletes its sprints (ON DELETE CASCADE).

**Relationship 5: Team-to-Project**

- Type: One-to-Many
- Description: A team's larger features (epics) are its projects.
- Implementation: Through the `team_id` foreign key in the projects table.
- Deletion behavior: Deleting a team deletes its projects (ON DELETE CASCADE).

**Relationship 6: Project-to-Issue**

- Type: One-to-Many (optional)
- Description: A project groups the issues that deliver one feature; an issue belongs to at most one project.
- Implementation: Through the nullable `project_id` foreign key in the issues table. The project must belong to the same team as the issue (enforced at application level).
- Deletion behavior: Deleting a project keeps its issues; they only lose the parent (ON DELETE SET NULL).

**Relationship 7: Sprint-to-Issue**

- Type: One-to-Many (optional)
- Description: An issue is planned in at most one sprint at a time; an issue with no sprint is in the backlog.
- Implementation: Through the nullable `sprint_id` foreign key in the issues table. The sprint must belong to the same team as the issue (enforced at application level).
- Deletion behavior: Deleting a sprint keeps its issues and moves them back to the backlog (ON DELETE SET NULL).

**Relationship 8: Team-to-View**

- Type: One-to-Many
- Description: A view is a saved filter over one team's issues, owned by the user who made it and optionally shared with the workspace.
- Implementation: Through the `team_id` and `owner_id` foreign keys in the views table.
- Deletion behavior: Deleting the team or the owner deletes the view (ON DELETE CASCADE).

**Relationship 9: Issue-to-Comment**

- Type: One-to-Many
- Description: Each issue can have an ongoing conversation thread consisting of multiple comments.
- Implementation: Through `issue_id` foreign key in the comments table.
- Creation requirement: All resources must be created by authenticated users (enforced at application level)
- Nesting logic: Includes a self-referencing `parent_id` to support threaded replies within the same issue.
- Deletion behavior: Deleting an issue removes all related comments. Deleting a parent comment removes all nested replies (ON DELETE CASCADE).

**Relationship 10: Issue-to-Activity**

- Type: One-to-Many
- Description: Every change to an issue is recorded as an activity row, shown as the issue's history.
- Implementation: Through the `issue_id` foreign key in the issue_activities table. Rows are written by the API in the same transaction as the change.
- Deletion behavior: Deleting an issue removes its history (ON DELETE CASCADE). Deleting a user keeps the history but clears the actor (ON DELETE SET NULL).

**Relationship 11: Issue-to-Attachment**

- Type: One-to-Many
- Description: An issue can have multiple supporting files, images, or documents attached to it.
- Implementation: Through `issue_id` foreign key in the attachments table.
- Storage requirement: The database stores metadata and a pointer (file_url), while the physical file resides in cloud storage.
- Deletion behavior: Deleting an issue removes the database record and triggers a cleanup of the physical file in storage.

**Relationship 12: User-to-Notification**

- Type: One-to-Many
- Description: A single user receives multiple alerts based on mentions, assignments, or status updates, from any of their workspaces.
- Implementation: Through `user_id` foreign key in the notifications table.
- Creation requirement: Entries are typically generated via a Kafka event consumer when a relevant action occurs elsewhere in the system.
- Deletion behavior: Notifications are removed if the recipient user is deleted (ON DELETE CASCADE).

---

## Notes on Implementation

1. **Foreign Key Constraints**
   - Every relationship uses hard foreign keys in PostgreSQL to ensure data integrity at the database level.

2. **Performance**
   - All "Many" sides of these relationships (e.g., issue_id in comments) are indexed to ensure that loading an issue page remains fast even with thousands of comments.

3. **Microservices Decoupling**
   - While these are DB relationships, the Notification and Search logic use an Event-Driven approach. The database stores the state, but Kafka moves the data between the "Action" and the "Alert."

4. **Workspace scoping**
   - Every API path starts with the workspace slug (`/w/{slug}/...`). The API first checks that the caller is in `workspace_members` for that workspace (otherwise 404), and every query below that is limited to the workspace's teams. This is what keeps one company's data invisible to another.
