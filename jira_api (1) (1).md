# TaskManagement API Documentation

---

## Table of Contents

- [TaskManagement API Documentation](#taskmanagement-api-documentation)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [API Endpoints](#api-endpoints)
    - [0. Conventions](#0-conventions)
      - [Objects](#objects)
    - [1. User Management Endpoints](#1-user-management-endpoints)
      - [1.1. Sign in with Google](#11-sign-in-with-google)
      - [1.2. Refresh Token](#12-refresh-token)
      - [1.3. Logout (Client-side)](#13-logout-client-side)
      - [1.4. Get User Profile](#14-get-user-profile)
      - [1.5. Update User Profile](#15-update-user-profile)
    - [2. Workspace and Member Endpoints](#2-workspace-and-member-endpoints)
      - [2.1. List My Workspaces](#21-list-my-workspaces)
      - [2.2. Create Workspace](#22-create-workspace)
      - [2.3. Get and Update Workspace](#23-get-and-update-workspace)
      - [2.4. Delete Workspace](#24-delete-workspace)
      - [2.5. List Members](#25-list-members)
      - [2.6. Manage Members](#26-manage-members)
    - [3. Team Endpoints](#3-team-endpoints)
      - [3.1. List Teams](#31-list-teams)
      - [3.2. Create Team](#32-create-team)
      - [3.3. Get, Update and Delete Team](#33-get-update-and-delete-team)
      - [3.4. Get Team Summary](#34-get-team-summary)
      - [3.5. Get Team Backlog](#35-get-team-backlog)
      - [3.6. Get Team Board](#36-get-team-board)
      - [3.7. Get Team Issue List](#37-get-team-issue-list)
      - [3.8. Get Team Timeline](#38-get-team-timeline)
      - [3.9. Get Team Calendar](#39-get-team-calendar)
      - [3.10. Get Team Development](#310-get-team-development)
      - [3.11. Get Archived Work](#311-get-archived-work)
    - [4. Sprint (Cycle) Endpoints](#4-sprint-cycle-endpoints)
      - [4.1. Create Sprint](#41-create-sprint)
      - [4.2. Get and Update Sprint](#42-get-and-update-sprint)
      - [4.3. Start Sprint](#43-start-sprint)
      - [4.4. Complete Sprint](#44-complete-sprint)
      - [4.5. Get Team Sprints](#45-get-team-sprints)
      - [4.6. Get Sprint Issues](#46-get-sprint-issues)
      - [4.7. Add Issues to Sprint](#47-add-issues-to-sprint)
      - [4.8. Delete Sprint](#48-delete-sprint)
    - [5. Project Endpoints](#5-project-endpoints)
      - [5.1. List Team Projects](#51-list-team-projects)
      - [5.2. Create Project](#52-create-project)
      - [5.3. Get and Update Project](#53-get-and-update-project)
      - [5.4. Get Project Issues](#54-get-project-issues)
      - [5.5. Delete Project](#55-delete-project)
    - [6. Issue Operations Endpoints](#6-issue-operations-endpoints)
      - [6.1. Create Issue](#61-create-issue)
      - [6.2. Get Issue Details](#62-get-issue-details)
      - [6.3. Update Issue Details](#63-update-issue-details)
      - [6.4. Move Issue Status](#64-move-issue-status)
      - [6.5. Get Issue Activity](#65-get-issue-activity)
      - [6.6. List Issue Comments](#66-list-issue-comments)
      - [6.7. Add Issue Comment](#67-add-issue-comment)
      - [6.8. Edit and Delete Comment](#68-edit-and-delete-comment)
      - [6.9. Bulk Update Issues](#69-bulk-update-issues)
      - [6.10. Bulk Delete Issues](#610-bulk-delete-issues)
      - [6.11. Delete Issue](#611-delete-issue)
    - [7. View Endpoints](#7-view-endpoints)
      - [7.1. List Team Views](#71-list-team-views)
      - [7.2. Create View](#72-create-view)
      - [7.3. Get, Update and Delete View](#73-get-update-and-delete-view)
      - [7.4. Get View Issues](#74-get-view-issues)
    - [8. Artificial Intelligence Endpoints](#8-artificial-intelligence-endpoints)
      - [8.1. Semantic Issue Search](#81-semantic-issue-search)
      - [8.2. AI Team Assistant](#82-ai-team-assistant)
      - [8.3. Issue Summary Generation](#83-issue-summary-generation)
    - [9. Attachment Management Endpoints](#9-attachment-management-endpoints)
      - [9.1. Request Upload URL](#91-request-upload-url)
      - [9.2. Confirm Upload Completion](#92-confirm-upload-completion)
      - [9.3. Get Attachment Preview](#93-get-attachment-preview)
      - [9.4. List Issue Attachments](#94-list-issue-attachments)
    - [10. Notification Endpoints](#10-notification-endpoints)
      - [10.1. Get Unread Count](#101-get-unread-count)
      - [10.2. Connect to Notification Stream](#102-connect-to-notification-stream)
      - [10.3. Mark All as Read](#103-mark-all-as-read)
    - [11. Analytics Endpoints](#11-analytics-endpoints)
      - [11.1. Get Velocity Chart](#111-get-velocity-chart)
      - [11.2. Get Burn-down Data](#112-get-burn-down-data)
      - [11.3. AI Predicted Bottlenecks](#113-ai-predicted-bottlenecks)
  - [Environment Variables](#environment-variables)

---

## Overview

This document outlines the API endpoints for the **TaskManagement** service. All paths are served under `/api` (e.g. `POST /api/auth/google`). The resources follow the structure in the schema doc:

```
User
 ├── Workspace ── Members
 │    └── Teams ── Issues (Comments, Activities, Attachments)
 │              ├─ Sprints (Cycles)
 │              ├─ Projects (features / epics; the issues' parent)
 │              └─ Views (saved filters)
 └── Notifications
```

TaskManagement allows users to:

1. **User Management**
   1. Sign up and log in with Google (the only login method)
   2. Secure sessions using JWT authentication with refresh token support
   3. Manage their own profile

2. **Workspaces and Members**
   1. Create workspaces and switch between the ones they belong to
   2. Add members and give them a workspace role (Admin or Member)

3. **Teams**
   1. Split a workspace into teams, each with its own issue keys (`ENG-12`)
   2. See each team's work through a summary, backlog, board and issue list

4. **Sprints and Projects**
   1. Plan a team's work in time-boxed sprints (cycles)
   2. Group issues into projects (features / epics) with a lead, status and target date

5. **Issue Operations**
   1. Create and track individual tasks (Issues) with detailed descriptions
   2. Manage workflow stages by moving issues across status columns
   3. Foster collaboration through threaded comments, and see every change in the issue's activity history

6. **Views**
   1. Save a filter over a team's issues and reopen it later
   2. Share a view with the whole workspace, or keep it private

7. **Artificial Intelligence**
   1. Execute Semantic Search to find information based on intent rather than just keywords
   2. Use "Ask AI" for natural language querying of team data
   3. Generate instant ticket summaries and receive real-time streaming AI responses

8. **Attachment Management**
   1. Request secure upload URLs for file handling
   2. Store and preview attachments linked directly to issues
   3. Maintain a organized list of all assets associated with specific tasks

9. **Notifications**
   1. Track unread activity counts across all of the user's workspaces
   2. Connect to a real-time notification stream for instant updates
   3. Perform bulk actions like marking all alerts as read

10. **Analytics**
    1. Monitor team performance with Velocity Charts and Burn-down data
    2. Leverage AI to predict and identify potential bottlenecks
    3. Access data-driven insights to optimize sprint planning

---

## API Endpoints

### 0. Conventions

**Status:** sections 1–7 are the core API. The code still implements the previous layout (projects, epics, no workspaces) and will be rebuilt to match this document. Sections 8–11 are planned.

- **Auth:** every endpoint except register, login and refresh needs `Authorization: Bearer {access_token}`. Access tokens last 1 hour; a refresh token (7 days) trades for a new one.
- **Workspace in the path:** everything that lives inside a workspace is under `/w/{slug}/...` (e.g. `/w/acme/teams`). Only the account (`/auth`, `/users/me`), the workspace list and notifications are outside it.
- **Roles:** one per workspace, in `workspace_members.role`. There is no team membership: every member can work in every team of the workspace.
  - **Member:** read everything in the workspace; create and edit issues, comments, sprints, projects and views.
  - **Admin:** everything a Member can, plus workspace settings, members and roles, creating/editing/deleting teams, deleting sprints and anyone's issues or comments.
- **Hidden means 404:** a workspace you're not a member of (and everything in it) answers `404`, not `403`, so outsiders can't learn it exists. `403` means "you can see it, but your role can't do this".
- **Teams in paths use their key:** `/w/acme/teams/ENG/...`. Keys are unique within a workspace and never change.
- **Issue keys** like `ENG-12` are the team key plus the issue number. They're case-insensitive in paths (`/w/acme/issues/eng-12` works).
- **PATCH** changes only the fields sent. Sending a field as `null` clears it where that's allowed (e.g. `assignee_id`).
- **Errors** look like `{"detail": "Only workspace Admins can do this"}`. `422` = the request breaks a rule (bad value, project in another team, ...); `409` = it conflicts with the current state (duplicate key, sprint already active, last Admin, ...).
- **Values:** `status` = `todo` | `in_progress` | `in_review` | `done` ("backlog" = `sprint_id` is null). `priority` = 1 Highest, 2 High, 3 Medium, 4 Low, 5 Lowest. `issue_type` = `task` | `bug` | `story`. Project `status` = `planned` | `in_progress` | `paused` | `completed` | `canceled`.

#### Objects

These shapes are returned by many endpoints below.

**User**

```json
{ "id": 42, "email": "henry@example.com", "username": "henry_dev", "name": "Henry", "created_at": "2026-05-29T14:30:00Z" }
```

**Workspace**: `role` is the caller's own role in it.

```json
{ "id": 3, "name": "Acme Inc", "slug": "acme", "role": "Admin", "member_count": 12, "created_at": "2026-01-10T09:00:00Z", "updated_at": "2026-01-10T09:00:00Z" }
```

**Member**: a User plus their role in this workspace.

```json
{ "user_id": 88, "username": "lydiagao", "name": "Lydia Gao", "email": "lydia@example.com", "role": "Member", "joined_at": "2026-01-20T10:00:00Z" }
```

**Team**: `issue_count` is how many issues exist now.

```json
{
  "id": 101,
  "workspace_id": 3,
  "name": "Engineering",
  "key": "ENG",
  "description": "Backend and infrastructure.",
  "is_archived": false,
  "issue_count": 42,
  "created_at": "2026-01-15T09:00:00Z",
  "updated_at": "2026-05-01T12:00:00Z"
}
```

**Project**: `progress` counts the project's issues.

```json
{
  "id": 380,
  "team_id": 101,
  "name": "Kafka migration",
  "description": "Move the event bus from Zookeeper to KRaft.",
  "status": "in_progress",
  "lead_id": 42,
  "start_date": "2026-05-01",
  "target_date": "2026-06-30",
  "progress": { "total": 9, "done": 4 },
  "created_at": "2026-04-20T09:00:00Z",
  "updated_at": "2026-05-10T12:00:00Z"
}
```

**Issue**: people, the project and the sprint are ids; the client looks them up in the lists it already has. `issue_key` is built from the team key and `number`.

```json
{
  "id": 402,
  "issue_key": "ENG-402",
  "team_id": 101,
  "number": 402,
  "issue_type": "task",
  "project_id": 380,
  "sprint_id": 12345,
  "title": "Configure Kafka KRaft mode",
  "description": "Migration from Zookeeper to KRaft for the event bus.",
  "status": "todo",
  "priority": 2,
  "assignee_id": 42,
  "reporter_id": 88,
  "story_points": 3,
  "labels": ["infra", "kafka"],
  "due_date": "2026-06-10T23:59:59Z",
  "created_at": "2026-05-29T20:45:00Z",
  "updated_at": "2026-05-29T20:45:00Z"
}
```

**Sprint**

```json
{
  "id": 12345,
  "team_id": 101,
  "name": "Sprint 1",
  "goal": "Complete the user authentication module",
  "status": "planned",
  "start_date": "2026-06-15T09:00:00Z",
  "end_date": "2026-06-29T17:00:00Z",
  "completed_date": null,
  "created_by": 42,
  "created_at": "2026-06-10T10:00:00Z"
}
```

**Comment**: replies carry `parent_id`.

```json
{ "id": 501, "issue_id": 402, "author_id": 42, "parent_id": null, "content": "The Redis cache-aside logic is passing.", "is_edited": false, "created_at": "2026-05-29T21:25:00Z", "updated_at": "2026-05-29T21:25:00Z" }
```

**Activity**: one change to an issue. `field` is null for `created`.

```json
{ "id": 9001, "issue_id": 402, "actor_id": 42, "action": "updated", "field": "status", "old_value": "todo", "new_value": "in_progress", "created_at": "2026-05-30T09:12:00Z" }
```

**View**

```json
{
  "id": 77,
  "team_id": 101,
  "owner_id": 42,
  "name": "My urgent bugs",
  "filters": { "issue_type": ["bug"], "priority": [1, 2], "assignee_id": [42], "status": ["todo", "in_progress"] },
  "is_shared": false,
  "created_at": "2026-05-01T10:00:00Z",
  "updated_at": "2026-05-01T10:00:00Z"
}
```

---

### 1. User Management Endpoints

The account itself. It isn't inside any workspace.

#### 1.1. Sign in with Google

**Purpose:** Log in, or sign up, with Google. This is the only way to log in: there are no passwords. The frontend's Sign in with Google button gives it a Google ID token (the "credential"); the backend checks it was signed by Google for our client ID (`GOOGLE_CLIENT_ID`) and that Google verified the email.

- **Known user** (matched by Google account): logged in.
- **Account from before Google login** (no Google account linked yet, same email): linked to this Google account, then logged in.
- **New user, no `username` sent:** nothing is created; the response is `signup_required` with the Google email and name, so the app can ask for a username (and a display name, prefilled).
- **New user with `username`:** the app sends the same Google token again with `username` (and optional `name`, which defaults to the Google name). The account is created with the Google email and logged in. Like any new account it belongs to no workspace yet: the user then creates one (2.2) or is added to one by an Admin (2.6).

**Endpoint:** `/auth/google`

**Method:** `POST`

**Request Body:** (`username` and `name` only when creating an account)

```json
{
  "token": "eyJhbGciOiJSUzI1NiIsImtpZCI6Ij...",
  "username": "henry_dev",
  "name": "Henry"
}
```

**Response:** (200 OK) logged in:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { "id": 42, "email": "henry@example.com", "username": "henry_dev", "name": "Henry", "created_at": "2026-05-29T14:30:00Z" }
}
```

or (200 OK) a new user without `username`:

```json
{ "signup_required": true, "email": "henry@example.com", "name": "Henry Dev" }
```

**Errors:** 401 invalid or expired Google token, or email not verified by Google · 409 username taken, or the email belongs to an account linked to a different Google account

**Swagger:** there is no login form; its Authorize button takes an access token (from this endpoint's response) pasted as a Bearer token.

---

#### 1.2. Refresh Token

**Purpose:** Get a new access token using a refresh token. An access token is rejected here, and a refresh token is rejected everywhere else.

**Endpoint:** `/auth/refresh`

**Method:** `POST`

**Request Body:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** (200 OK)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Errors:** 401 invalid, expired, or not a refresh token

---

#### 1.3. Logout (Client-side)

**Purpose:** Client removes tokens from storage. No server-side action required with pure JWT.

**Note:** In a pure JWT implementation, logout is handled client-side by removing the tokens from storage. The frontend application should delete both the access token and refresh token from localStorage or cookies when the user logs out, and then redirect to the login page.

---

#### 1.4. Get User Profile

**Purpose:** The current user, plus each workspace they belong to with their role there. The frontend uses the list for the workspace switcher and opens the first one after login.

**Endpoint:** `/users/me`

**Method:** `GET`

**Response:** (200 OK)

```json
{
  "id": 42,
  "email": "henry@example.com",
  "username": "henry_dev",
  "name": "Henry",
  "created_at": "2026-05-29T14:30:00Z",
  "workspaces": [
    { "id": 3, "name": "Acme Inc", "slug": "acme", "role": "Admin" },
    { "id": 7, "name": "Side project", "slug": "side-project", "role": "Member" }
  ]
}
```

---

#### 1.5. Update User Profile

**Purpose:** Update the current user's username, email, or display name.

**Endpoint:** `/users/me`

**Method:** `PATCH`

**Request Body:**

```json
{
  "username": "henry_updated",
  "email": "new_henry@example.com",
  "name": "Henry D."
}
```

**Response:** (200 OK) a **User**.

**Errors:** 409 email or username taken

---

### 2. Workspace and Member Endpoints

#### 2.1. List My Workspaces

**Purpose:** The workspaces the current user belongs to, for the workspace switcher.

**Endpoint:** `/workspaces`

**Method:** `GET`

**Response:** (200 OK) a list of **Workspace**.

---

#### 2.2. Create Workspace

**Purpose:** Create a workspace. Any logged-in user can; the creator becomes its first Admin. The slug is the workspace's address (`/w/acme`): 3–32 characters, lowercase letters, digits and dashes.

**Endpoint:** `/workspaces`

**Method:** `POST`

**Request Body:**

```json
{
  "name": "Acme Inc",
  "slug": "acme"
}
```

**Response:** (201 Created) the new **Workspace**.

**Errors:** 409 slug taken · 422 invalid slug

---

#### 2.3. Get and Update Workspace

**Purpose:** Read the workspace, or rename it / change its slug (Admins only). Changing the slug changes every link into the workspace, so the frontend should warn first.

**Endpoint:** `/w/{slug}`

**Method:** `GET` · `PATCH`

**Request Body:** (PATCH)

```json
{
  "name": "Acme Corporation",
  "slug": "acme-corp"
}
```

**Response:** (200 OK) the **Workspace**.

**Errors:** 403 not an Admin · 404 not a member · 409 slug taken · 422 invalid slug

---

#### 2.4. Delete Workspace

**Purpose:** Delete a workspace with all its teams, issues, sprints, projects, views and memberships. Admins only. The users' accounts are kept.

**Endpoint:** `/w/{slug}`

**Method:** `DELETE`

**Response:** (204 No Content)

**Errors:** 403 not an Admin

---

#### 2.5. List Members

**Purpose:** Everyone in the workspace (for assignee and lead pickers, and the members settings page).

**Endpoint:** `/w/{slug}/members`

**Method:** `GET`

**Response:** (200 OK) a list of **Member**.

---

#### 2.6. Manage Members

**Purpose:** Add an existing user (by username or email), change a member's role, or remove a member. Admins only, except that anyone may remove themselves (leave). A workspace always keeps at least one Admin. Removing someone keeps their issues and comments; issues assigned to them stay assigned (the assignee shows as a former member).

| Action      | Method   | Endpoint                         | Body                                            | Response            |
| ----------- | -------- | -------------------------------- | ----------------------------------------------- | ------------------- |
| Add         | `POST`   | `/w/{slug}/members`              | `{ "username_or_email": "lydiagao", "role": "Member" }` | 201, the **Member** |
| Change role | `PATCH`  | `/w/{slug}/members/{user_id}`    | `{ "role": "Admin" }`                           | 200, the **Member** |
| Remove      | `DELETE` | `/w/{slug}/members/{user_id}`    |                                                 | 204                 |

Email invitations for people without an account are **planned**.

**Errors:** 403 not an Admin · 404 not a member · 409 already a member, or would remove/demote the last Admin · 422 no user with that username or email

---

### 3. Team Endpoints

#### 3.1. List Teams

**Purpose:** The teams of the workspace. Populates the sidebar.

**Endpoint:** `/w/{slug}/teams`

**Method:** `GET`

**Response:** (200 OK) a list of **Team**.

---

#### 3.2. Create Team

**Purpose:** Create a team. Admins only. The key (2–10 characters, capital letters and digits, starting with a letter) prefixes every issue key (`ENG-12`), is unique within the workspace, and is permanent.

**Endpoint:** `/w/{slug}/teams`

**Method:** `POST`

**Request Body:**

```json
{
  "name": "Engineering",
  "key": "ENG",
  "description": "Backend and infrastructure."
}
```

**Response:** (201 Created) the new **Team**.

**Errors:** 403 not an Admin · 409 key taken in this workspace · 422 invalid key

---

#### 3.3. Get, Update and Delete Team

**Purpose:** Read a team; rename it, change its description, or archive it (Admins); or delete it with all its issues, comments, sprints, projects and views (Admins). The key can't be changed.

**Endpoint:** `/w/{slug}/teams/{team_key}`

**Method:** `GET` · `PATCH` · `DELETE`

**Request Body:** (PATCH)

```json
{
  "name": "Platform Engineering",
  "description": "Phase two",
  "is_archived": false
}
```

**Response:** (200 OK) the **Team**; DELETE answers 204 No Content.

**Errors:** 403 not an Admin · 404 team not found

---

#### 3.4. Get Team Summary

**Purpose:** High-level counts of a team's health.

**Endpoint:** `/w/{slug}/teams/{team_key}/summary`

**Method:** `GET`

**Response:** (200 OK) (`days_remaining` counts down to the active sprint's end; `null` without an active sprint)

```json
{
  "team_id": 101,
  "name": "Engineering",
  "active_sprint_id": 12345,
  "stats": {
    "open_issues": 24,
    "completed_issues": 115,
    "active_projects": 3,
    "days_remaining": 9
  }
}
```

---

#### 3.5. Get Team Backlog

**Purpose:** Unfinished issues that aren't planned in any sprint (`sprint_id` null, status not `done`), most urgent first.

**Endpoint:** `/w/{slug}/teams/{team_key}/backlog`

**Method:** `GET`

**Response:** (200 OK) a list of **Issue**, ordered by priority, then number.

---

#### 3.6. Get Team Board

**Purpose:** The sprint board: the active sprint's issues in one column per status. With no active sprint, `sprint_id` is null and the columns are empty.

**Endpoint:** `/w/{slug}/teams/{team_key}/board`

**Method:** `GET`

**Response:** (200 OK) (each `issues` item is a full **Issue**, shortened here)

```json
{
  "team_id": 101,
  "sprint_id": 12345,
  "columns": [
    { "id": "todo", "name": "To Do", "issues": [{ "issue_key": "ENG-12", "title": "Setup VPC Peering", "priority": 2, "issue_type": "task", "assignee_id": null }] },
    { "id": "in_progress", "name": "In Progress", "issues": [{ "issue_key": "ENG-10", "title": "Write Dockerfiles", "priority": 3, "issue_type": "story", "assignee_id": 42 }] },
    { "id": "in_review", "name": "In Review", "issues": [] },
    { "id": "done", "name": "Done", "issues": [] }
  ]
}
```

---

#### 3.7. Get Team Issue List

**Purpose:** Every issue of the team, newest first, narrowed by any filters given. Repeat a parameter to match any of several values (`status=todo&status=in_progress`); the same parameters are what a View saves (7).

**Endpoint:** `/w/{slug}/teams/{team_key}/issues`

**Method:** `GET`

**Query Parameters:** (all optional)

- `status`: `todo` | `in_progress` | `in_review` | `done`
- `priority`: Integer 1-5
- `issue_type`: `task` | `bug` | `story`
- `assignee_id`: Integer
- `project_id`: Integer
- `sprint_id`: Integer
- `labels`: String
- `search`: String; matches the title or the key, ignoring case (`search=kafka`, `search=eng-40`)

**Response:** (200 OK) a list of **Issue**.

---

#### 3.8. Get Team Timeline

**Planned.** Built from the team's projects (their `start_date` and `target_date`) and sprints.

**Purpose:** The team's roadmap: projects and sprints laid out on a time axis.

**Endpoint:** `/w/{slug}/teams/{team_key}/timeline`

**Method:** `GET`

---

#### 3.9. Get Team Calendar

**Planned.** Issue deadlines come from `issues.due_date`; meeting events need a table first.

**Purpose:** Fetch all date-bound tasks, sprint deadlines, and launch events organized chronologically by date.

**Endpoint:** `/w/{slug}/teams/{team_key}/calendar`

**Method:** `GET`

---

#### 3.10. Get Team Development

**Planned.** Needs a repository integration.

**Purpose:** Retrieve integrations, repository URLs, build/deployment statuses, and CI/CD pipelines connected to the team.

**Endpoint:** `/w/{slug}/teams/{team_key}/development`

**Method:** `GET`

---

#### 3.11. Get Archived Work

**Planned.**

**Purpose:** Access historic, archived issues, completed projects, or completed sprint history no longer active on the live boards.

**Endpoint:** `/w/{slug}/teams/{team_key}/archive`

**Method:** `GET`

---

### 4. Sprint (Cycle) Endpoints

Any member can create, edit, start and complete sprints; deleting one needs an Admin.

#### 4.1. Create Sprint

**Purpose:** Create a new sprint within a team. Sprints are created in the `planned` state.

**Endpoint:** `/w/{slug}/teams/{team_key}/sprints`

**Method:** `POST`

**Request Body:** (`goal` and the dates are optional; they're needed before the sprint can start)

```json
{
  "name": "Sprint 1",
  "goal": "Complete the user authentication module",
  "start_date": "2026-06-15T09:00:00Z",
  "end_date": "2026-06-29T17:00:00Z"
}
```

**Response:** (201 Created) the new **Sprint**.

**Errors:** 404 team not found · 422 `end_date` not after `start_date`

---

#### 4.2. Get and Update Sprint

**Purpose:** Read one sprint, or update its name, goal, or dates. A completed sprint can't be changed.

**Endpoint:** `/w/{slug}/sprints/{sprint_id}`

**Method:** `GET` · `PATCH`

**Request Body:** (PATCH)

```json
{
  "name": "Sprint 1 - Updated",
  "goal": "Complete user auth and basic profile views"
}
```

**Response:** (200 OK) the **Sprint**.

**Errors:** 404 sprint not found · 409 sprint is completed · 422 invalid dates

---

#### 4.3. Start Sprint

**Purpose:** Move a sprint from `planned` to `active`.

**Endpoint:** `/w/{slug}/sprints/{sprint_id}/start`

**Method:** `POST`

**Response:** (200 OK) the **Sprint** with `"status": "active"`.

**Errors:** 404 sprint not found · 409 sprint is not `planned`, lacks a start/end date, or the team already has an active sprint (the database's partial unique index decides, so two people pressing Start at once can't both win)

---

#### 4.4. Complete Sprint

**Purpose:** Move an active sprint to `completed`. Its `done` issues stay with it; unfinished issues move to the destination sprint, or to the backlog. Each moved issue gets a `sprint_id` activity row.

**Endpoint:** `/w/{slug}/sprints/{sprint_id}/complete`

**Method:** `POST`

**Request Body:**

| Field                 | Type            | Description                                                                       |
| --------------------- | --------------- | --------------------------------------------------------------------------------- |
| destination_sprint_id | integer \| null | A planned sprint of the same team to move unfinished issues to; `null` = backlog |

```json
{
  "destination_sprint_id": 98765
}
```

**Response:** (200 OK)

```json
{
  "id": 12345,
  "status": "completed",
  "completed_date": "2026-06-29T17:05:00Z",
  "completed_issues": 8,
  "moved_issues": 3
}
```

**Errors:** 404 sprint not found · 409 sprint is not `active` · 422 destination is not a planned sprint of this team

---

#### 4.5. Get Team Sprints

**Purpose:** List the sprints of a team, newest first.

**Endpoint:** `/w/{slug}/teams/{team_key}/sprints`

**Method:** `GET`

**Query Parameters:**

- `status`: `planned` | `active` | `completed` (optional)
- `limit`: integer 1-200, default 50

**Response:** (200 OK) a list of **Sprint**.

---

#### 4.6. Get Sprint Issues

**Purpose:** List the issues planned in a sprint, most urgent first.

**Endpoint:** `/w/{slug}/sprints/{sprint_id}/issues`

**Method:** `GET`

**Response:** (200 OK) a list of **Issue**.

---

#### 4.7. Add Issues to Sprint

**Purpose:** Move existing issues of the same team into a sprint (sets their `sprint_id`): all of them, or, if any key is invalid, none. To move an issue back to the backlog, `PATCH /w/{slug}/issues/{issue_key}` with `"sprint_id": null`.

**Endpoint:** `/w/{slug}/sprints/{sprint_id}/issues`

**Method:** `POST`

**Request Body:**

```json
{
  "issue_keys": ["ENG-12", "ENG-13"]
}
```

**Response:** (200 OK)

```json
{
  "sprint_id": 12345,
  "added": ["ENG-12", "ENG-13"]
}
```

**Errors:** 404 sprint not found · 409 sprint is `completed` · 422 an issue doesn't exist or belongs to another team

---

#### 4.8. Delete Sprint

**Purpose:** Delete a sprint. Its issues stay and go back to the backlog. Admins only.

**Endpoint:** `/w/{slug}/sprints/{sprint_id}`

**Method:** `DELETE`

**Response:** (204 No Content)

---

### 5. Project Endpoints

A project is a feature or epic inside a team; issues join it through `project_id`. Any member can create and edit projects.

#### 5.1. List Team Projects

**Purpose:** The projects of a team, with their progress.

**Endpoint:** `/w/{slug}/teams/{team_key}/projects`

**Method:** `GET`

**Query Parameters:**

- `status`: `planned` | `in_progress` | `paused` | `completed` | `canceled` (optional)

**Response:** (200 OK) a list of **Project**, ordered by `target_date` (projects without one last).

---

#### 5.2. Create Project

**Purpose:** Create a project in a team. Only `name` is required; the lead must be a workspace member.

**Endpoint:** `/w/{slug}/teams/{team_key}/projects`

**Method:** `POST`

**Request Body:**

```json
{
  "name": "Kafka migration",
  "description": "Move the event bus from Zookeeper to KRaft.",
  "status": "planned",
  "lead_id": 42,
  "start_date": "2026-05-01",
  "target_date": "2026-06-30"
}
```

**Response:** (201 Created) the new **Project**.

**Errors:** 404 team not found · 422 lead is not a member, or `target_date` before `start_date`

---

#### 5.3. Get and Update Project

**Purpose:** Read one project, or change its name, description, status, lead or dates. A project can't move to another team.

**Endpoint:** `/w/{slug}/projects/{project_id}`

**Method:** `GET` · `PATCH`

**Request Body:** (PATCH)

```json
{
  "status": "completed",
  "target_date": "2026-07-15"
}
```

**Response:** (200 OK) the **Project**.

**Errors:** 404 project not found · 422 invalid value, lead is not a member, or dates out of order

---

#### 5.4. Get Project Issues

**Purpose:** The issues of a project, most urgent first. To add or remove an issue, `PATCH` the issue's `project_id` (6.3).

**Endpoint:** `/w/{slug}/projects/{project_id}/issues`

**Method:** `GET`

**Response:** (200 OK) a list of **Issue**.

---

#### 5.5. Delete Project

**Purpose:** Delete a project. Its issues are kept; they just lose the project. Allowed for the project's lead and for Admins.

**Endpoint:** `/w/{slug}/projects/{project_id}`

**Method:** `DELETE`

**Response:** (204 No Content)

**Errors:** 403 not the lead or an Admin

---

### 6. Issue Operations Endpoints

**Link rules** (checked on create, update, and bulk update, against the issue as it would be after the change; breaking one answers 422):

- the assignee is a member of the workspace
- the project belongs to the same team as the issue
- the sprint belongs to the same team and isn't completed

**Activity:** every create and every changed field (including through 6.4, 6.9, 4.4 and 4.7) writes one **Activity** row in the same transaction, so the history can never disagree with the issue. A PATCH that sends a field with its current value writes nothing for it.

#### 6.1. Create Issue

**Purpose:** Create a work item in a team. It gets the team's next number (`ENG-403`); numbers are never reused, even after a delete. The creator becomes the reporter.

**Endpoint:** `/w/{slug}/teams/{team_key}/issues`

**Method:** `POST`

**Request Body:** (only `title` is required; the rest shows the defaults or examples)

```json
{
  "title": "Configure Kafka KRaft mode",
  "description": "Migration from Zookeeper to KRaft for the event bus.",
  "issue_type": "task",
  "status": "todo",
  "priority": 3,
  "assignee_id": 42,
  "project_id": 380,
  "sprint_id": null,
  "story_points": 0,
  "labels": ["infra"],
  "due_date": null
}
```

Labels are trimmed and merged ignoring case (`["Bug", "bug"]` → `["Bug"]`); at most 5.

**Response:** (201 Created) the new **Issue**.

**Errors:** 404 team not found · 422 a link rule or a value is invalid

---

#### 6.2. Get Issue Details

**Purpose:** One issue, or every issue in the workspace (most recently updated first; use 3.7 for one team with filters).

**Endpoint:** `/w/{slug}/issues/{issue_key}` · `/w/{slug}/issues`

**Method:** `GET`

**Query Parameters:** (list only, optional)

- `assignee_id`: Integer (`assignee_id={my id}` gives "My issues" across all teams)

**Response:** (200 OK) an **Issue**, or a list of **Issue**.

---

#### 6.3. Update Issue Details

**Purpose:** Change any of an issue's fields except its team (moving teams would change its key).

**Endpoint:** `/w/{slug}/issues/{issue_key}`

**Method:** `PATCH`

**Request Body:**

```json
{
  "status": "in_review",
  "priority": 3,
  "project_id": null
}
```

**Response:** (200 OK) the updated **Issue**.

**Errors:** 404 not found · 422 a link rule or a value is invalid

---

#### 6.4. Move Issue Status

**Purpose:** Dedicated endpoint for board drag-and-drop: only the status changes.

**Endpoint:** `/w/{slug}/issues/{issue_key}/status`

**Method:** `PUT`

**Request Body:**

```json
{
  "status": "done"
}
```

**Response:** (200 OK)

```json
{
  "issue_key": "ENG-402",
  "status": "done",
  "updated_at": "2026-05-29T21:20:00Z"
}
```

---

#### 6.5. Get Issue Activity

**Purpose:** The issue's history, oldest first: when it was created and every change since. The issue page merges it with the comments into one timeline.

**Endpoint:** `/w/{slug}/issues/{issue_key}/activity`

**Method:** `GET`

**Response:** (200 OK) a list of **Activity**.

```json
[
  { "id": 9000, "issue_id": 402, "actor_id": 88, "action": "created", "field": null, "old_value": null, "new_value": null, "created_at": "2026-05-29T20:45:00Z" },
  { "id": 9001, "issue_id": 402, "actor_id": 42, "action": "updated", "field": "status", "old_value": "todo", "new_value": "in_progress", "created_at": "2026-05-30T09:12:00Z" },
  { "id": 9002, "issue_id": 402, "actor_id": 42, "action": "updated", "field": "assignee_id", "old_value": null, "new_value": 42, "created_at": "2026-05-30T09:13:00Z" }
]
```

---

#### 6.6. List Issue Comments

**Purpose:** All comments of an issue, oldest first, as a flat list. Replies carry `parent_id`, so the client nests them into threads.

**Endpoint:** `/w/{slug}/issues/{issue_key}/comments`

**Method:** `GET`

**Response:** (200 OK) a list of **Comment**.

---

#### 6.7. Add Issue Comment

**Purpose:** Add a comment to an issue. Send `parent_id` to reply to an existing comment of the same issue (threading).

**Endpoint:** `/w/{slug}/issues/{issue_key}/comments`

**Method:** `POST`

**Request Body:**

```json
{
  "content": "I've updated the Kafka producer settings.",
  "parent_id": null
}
```

**Response:** (201 Created) the new **Comment**.

**Errors:** 422 empty content, or the parent is on another issue

---

#### 6.8. Edit and Delete Comment

**Purpose:** Only the author can edit a comment (it's then marked `is_edited`). The author or an Admin can delete it; its replies are deleted with it.

| Action | Method   | Endpoint                            | Body                       | Response             |
| ------ | -------- | ----------------------------------- | -------------------------- | -------------------- |
| Edit   | `PATCH`  | `/w/{slug}/comments/{comment_id}`   | `{ "content": "Fixed." }`  | 200, the **Comment** |
| Delete | `DELETE` | `/w/{slug}/comments/{comment_id}`   |                            | 204                  |

---

#### 6.9. Bulk Update Issues

**Purpose:** Apply the same changes to many issues (e.g. from the List view). Each issue succeeds or fails on its own; one bad issue doesn't stop the rest. The issues may come from different teams of the workspace.

**Endpoint:** `/w/{slug}/issues/bulk`

**Method:** `PATCH`

**Request Body:** (`updates` may set `status`, `priority`, `assignee_id`, `project_id`, `sprint_id`; at most 100 keys)

```json
{
  "issue_keys": ["ENG-402", "ENG-405"],
  "updates": { "status": "in_review" }
}
```

**Response:** (200 OK)

```json
{
  "summary": {
    "total": 2,
    "success_count": 1,
    "failure_count": 1
  },
  "results": [
    {
      "issue_key": "ENG-402",
      "status": "Updated",
      "updated_at": "2026-05-29T21:55:00Z",
      "error": null
    },
    {
      "issue_key": "ENG-405",
      "status": "Failed",
      "updated_at": null,
      "error": "Sprint belongs to another team"
    }
  ]
}
```

---

#### 6.10. Bulk Delete Issues

**Purpose:** Delete many issues: all of them, or (if any key is missing or not allowed) none.

**Endpoint:** `/w/{slug}/issues/bulk`

**Method:** `DELETE`

**Request Body:**

```json
{
  "issue_keys": ["ENG-402", "ENG-405"]
}
```

**Response:** (204 No Content)

**Errors:** 403 not allowed to delete one of them (see 6.11) · 404 one of them doesn't exist

---

#### 6.11. Delete Issue

**Purpose:** Delete one issue with its comments, activity and attachments. Allowed for its reporter and for Admins.

**Endpoint:** `/w/{slug}/issues/{issue_key}`

**Method:** `DELETE`

**Response:** (204 No Content)

**Errors:** 403 not the reporter or an Admin

---

### 7. View Endpoints

A view is a saved filter over one team's issues. Its `filters` object uses the same names as the issue list's query parameters (3.7), with a list of accepted values per field. A private view is visible only to its owner; a shared one to the whole workspace. Only the owner can edit a view; the owner or an Admin can delete it.

#### 7.1. List Team Views

**Purpose:** The views of a team the caller can see: their own, plus every shared one.

**Endpoint:** `/w/{slug}/teams/{team_key}/views`

**Method:** `GET`

**Response:** (200 OK) a list of **View**.

---

#### 7.2. Create View

**Purpose:** Save the current filters as a view. The caller becomes its owner.

**Endpoint:** `/w/{slug}/teams/{team_key}/views`

**Method:** `POST`

**Request Body:**

```json
{
  "name": "My urgent bugs",
  "filters": { "issue_type": ["bug"], "priority": [1, 2], "assignee_id": [42] },
  "is_shared": false
}
```

**Response:** (201 Created) the new **View**.

**Errors:** 404 team not found · 422 unknown filter field or invalid value

---

#### 7.3. Get, Update and Delete View

**Purpose:** Read a view; rename it, change its filters, or share/unshare it (owner); or delete it (owner or Admin). Another user's private view answers 404.

**Endpoint:** `/w/{slug}/views/{view_id}`

**Method:** `GET` · `PATCH` · `DELETE`

**Request Body:** (PATCH)

```json
{
  "name": "Urgent bugs",
  "is_shared": true
}
```

**Response:** (200 OK) the **View**; DELETE answers 204 No Content.

**Errors:** 403 not the owner (or, for DELETE, not the owner or an Admin) · 404 not found or someone else's private view · 422 unknown filter field or invalid value

---

#### 7.4. Get View Issues

**Purpose:** Run the view: the team's issues matching its filters, newest first. Same result as 3.7 with the view's filters as query parameters.

**Endpoint:** `/w/{slug}/views/{view_id}/issues`

**Method:** `GET`

**Response:** (200 OK) a list of **Issue**.

---

### 8. Artificial Intelligence Endpoints

**Planned.**

#### 8.1. Semantic Issue Search

**Purpose:** Search for issues using natural language queries. Unlike standard keyword search, this uses vector embeddings to find relevant tasks even if the exact words don't match (e.g., searching "database lag" finds "Optimize Redis caching"). Leave out `team_key` to search the whole workspace.

**Endpoint:** `/w/{slug}/ai/search`

**Method:** `POST`

**Request Body:**

```json
{
  "team_key": "ENG",
  "query": "problems with message bus performance",
  "limit": 5
}
```

**Response:** (200 OK)

```json
{
  "query": "problems with message bus performance",
  "results": [
    {
      "issue_key": "ENG-402",
      "title": "Configure Kafka KRaft mode",
      "score": 0.92,
      "summary": "Migration to KRaft to improve metadata performance."
    },
    {
      "issue_key": "ENG-415",
      "title": "Investigate producer latency",
      "score": 0.85,
      "summary": "High latency observed in event-driven messaging service."
    }
  ]
}
```

---

#### 8.2. AI Team Assistant

**Purpose:** An interactive chat endpoint that answers questions about a team's status, blockers, or history. This uses Server-Sent Events (SSE) to stream the response back for a "typing" effect.

**Endpoint:** `/w/{slug}/ai/assistant`

**Method:** `POST`

**Headers:**

- `Accept: text/event-stream`

**Request Body:**

```json
{
  "team_key": "ENG",
  "message": "Which tasks are currently blocking the Kafka migration?",
  "stream": true
}
```

**Response:**

- 200 Stream of data chunks

---

#### 8.3. Issue Summary Generation

**Purpose:** Automatically generate a concise summary or "TL;DR" for an issue that has a long comment history.

**Endpoint:** `/w/{slug}/ai/summarize/{issue_key}`

**Method:** `POST`

**Response:** (200 OK)

```json
{
  "issue_key": "ENG-402",
  "summary": "The team is migrating Kafka to KRaft mode to remove Zookeeper dependency. Henry is currently debugging producer latency issues in the dev environment.",
  "generated_at": "2026-05-29T22:10:00Z"
}
```

---

### 9. Attachment Management Endpoints

**Planned.**

#### 9.1. Request Upload URL

**Purpose:** Obtain a temporary, pre-signed URL to upload a file directly to cloud storage. This keeps file traffic off your main application server.

**Endpoint:** `/w/{slug}/attachments/upload-url`

**Method:** `POST`

**Request Body:**

```json
{
  "issue_key": "ENG-402",
  "file_name": "architecture_diagram.png",
  "content_type": "image/png"
}
```

**Response:** (200 OK)

```json
{
  "upload_url": "https://storage.googleapis.com/planner-assets/temp-12345?signature=...",
  "file_id": "file_uuid_998",
  "expires_at": "2026-05-29T22:30:00Z"
}
```

---

#### 9.2. Confirm Upload Completion

**Purpose:** Notify the backend that the file has been successfully uploaded to the cloud. The backend then attaches the file record to the issue and moves it from "temp" to "permanent" storage.

**Endpoint:** `/w/{slug}/attachments/confirm`

**Method:** `POST`

**Request Body:**

```json
{
  "file_id": "file_uuid_998",
  "status": "success"
}
```

**Response:** (200 OK)

```json
{
  "issue_key": "ENG-402",
  "attachment": {
    "id": "file_uuid_998",
    "file_name": "architecture_diagram.png",
    "size_bytes": 1048576,
    "uploaded_at": "2026-05-29T22:15:00Z"
  }
}
```

---

#### 9.3. Get Attachment Preview

**Purpose:** Generate a secure, short-lived link to view or download an attachment. For images, this often points to a "thumbnail" version.

**Endpoint:** `/w/{slug}/attachments/{file_id}/preview`

**Method:** `GET`

**Response:** (200 OK)

```json
{
  "file_id": "file_uuid_998",
  "download_url": "https://storage.googleapis.com/planner-assets/perm/architecture_diagram.png?token=...",
  "thumbnail_url": "https://storage.googleapis.com/planner-assets/thumbs/architecture_diagram_sm.png",
  "expires_in_seconds": 3600
}
```

---

#### 9.4. List Issue Attachments

**Purpose:** Get a list of all files currently attached to a specific issue.

**Endpoint:** `/w/{slug}/issues/{issue_key}/attachments`

**Method:** `GET`

**Response:** (200 OK)

```json
[
  {
    "id": "file_uuid_998",
    "file_name": "architecture_diagram.png",
    "content_type": "image/png",
    "size_kb": 1024,
    "uploaded_by": "henry_dev",
    "uploaded_at": "2026-05-29T22:15:00Z"
  },
  {
    "id": "file_uuid_441",
    "file_name": "logs.txt",
    "content_type": "text/plain",
    "size_kb": 12,
    "uploaded_by": "lydiagao",
    "uploaded_at": "2026-05-28T10:05:00Z"
  }
]
```

---

### 10. Notification Endpoints

**Planned.** Notifications belong to the user, not to a workspace, so these paths have no `/w/{slug}` prefix; each notification's `link` includes its workspace (`/w/acme/issue/ENG-101`).

#### 10.1. Get Unread Count

**Purpose:** Fetch the current number of unread notifications to display as a "badge" count (e.g., the little red number over a bell icon) in the navigation bar.

**Endpoint:** `/notifications/unread-count`

**Method:** `GET`

**Response:** (200 OK)

```json
{
  "unread_count": 3,
  "last_checked_at": "2026-05-29T22:15:00Z"
}
```

---

#### 10.2. Connect to Notification Stream

**Purpose:** Establish a persistent, real-time connection. Instead of polling every 10 seconds, the server "pushes" new notifications to the client the moment they happen.

**Endpoint:** `/notifications/stream`

**Method:** `GET`

**Headers:**

- `Accept: text/event-stream`

- `Cache-Control: no-cache`

- `Connection: keep-alive`

**Response:**

- 200 Stream of data chunks

---

#### 10.3. Mark All as Read

**Purpose:** Clear the unread status for all notifications belonging to the current user. This is typically triggered when the user opens the notification panel.

**Endpoint:** `/notifications/read-all`

**Method:** `POST`

**Response:** (200 OK)

```json
{
  "status": "success",
  "marked_count": 3,
  "timestamp": "2026-05-29T22:25:00Z"
}
```

---

### 11. Analytics Endpoints

**Planned.**

#### 11.1. Get Velocity Chart

**Purpose:** Retrieve the amount of work (usually in Story Points) the team completes in each sprint. This helps in predicting how much work can be handled in future iterations.

**Endpoint:** `/w/{slug}/analytics/velocity`

**Method:** `GET`

**Query Parameters:**

- `team_key={key}` - Team to analyze (required)
- `period=day|week|month|year` - Time period for analytics (default: month)
- `start_date=YYYY-MM-DD` - Start date for custom range (optional)
- `end_date=YYYY-MM-DD` - End date for custom range (optional)

**Response:**

```json (200 OK)
{
  "team_id": 101,
  "period_type": "month",
  "range": {
    "start": "2026-01-01",
    "end": "2026-05-29"
  },
  "data": [
    {
      "label": "2026-01",
      "completed_count": 45,
      "story_points": 120
    },
    {
      "label": "2026-02",
      "completed_count": 38,
      "story_points": 110
    },
    {
      "label": "2026-03",
      "completed_count": 52,
      "story_points": 145
    }
  ],
  "totals": {
    "total_completed": 135,
    "average_per_period": 45
  }
}
```

---

#### 11.2. Get Burn-down Data

**Purpose:** Track the total work remaining in the current sprint. This endpoint provides the "Ideal" line versus the "Actual" remaining work. The actual line can be rebuilt from the `status` rows in issue activity.

**Endpoint:** `/w/{slug}/analytics/burndown`

**Method:** `GET`

**Query Parameters:**

- `sprint_id={id}` - sprint for analytics (default: current)

**Response:** (200 OK)

```json
{
  "sprint_id": 55,
  "start_date": "2026-05-15",
  "end_date": "2026-05-30",
  "data_points": [
    { "date": "2026-05-15", "ideal_remaining": 100, "actual_remaining": 100 },
    { "date": "2026-05-16", "ideal_remaining": 90, "actual_remaining": 95 },
    { "date": "2026-05-17", "ideal_remaining": 80, "actual_remaining": 75 }
  ]
}
```

---

#### 11.3. AI Predicted Bottlenecks

**Purpose:** Use an LLM to analyze the current distribution of tasks and identify likely delays (e.g., too many issues stuck in "In Review" or an overloaded assignee).

**Endpoint:** `/w/{slug}/analytics/ai-bottlenecks`

**Method:** `POST`

**Request Body:**

```json
{
  "team_key": "ENG",
  "include_historical_data": true
}
```

**Response:**

```json
{
  "bottlenecks": [
    {
      "type": "Stage Congestion",
      "location": "In Review",
      "severity": "High",
      "insight": "There are 8 tickets currently in 'In Review' with only 1 developer assigned as a reviewer. This is likely to delay the sprint goal."
    },
    {
      "type": "Resource Overload",
      "location": "User: henry_dev",
      "severity": "Medium",
      "insight": "Henry has 15 story points assigned for the next 3 days. Average completion rate suggests a 20% overflow risk."
    }
  ],
  "generated_at": "2026-05-29T22:30:00Z"
}
```

---

## Environment Variables

The application requires the following environment variables to be set:

| Variable           | Description                          | Default                            |
| ------------------ | ------------------------------------ | ---------------------------------- |
| DATABASE_URL       | Full PostgreSQL connection string    | postgresql+psycopg://user:pass@localhost:5433/taskmanagement |
| REDIS_URL          | Redis connection for caching/pub-sub | localhost:6379                     |
| KAFKA_BROKERS      | List of Kafka broker addresses       | localhost:9092                     |
| JWT_SECRET_KEY     | Secret key for signing JWTs          | None                               |
| JWT_ACCESS_EXPIRE  | Access token expiration in seconds   | 3600 (1 hour)                      |
| JWT_REFRESH_EXPIRE | Refresh token expiration in seconds  | 604800 (7 days)                    |
| LITELLM_BASE_URL   | URL of the LiteLLM proxy (holds the provider API keys) | http://localhost:4000             |
