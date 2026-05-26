-- PostgreSQL schema based on practical work 3.
-- Database: information system for cleaning process management at RTU MIREA.

CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    login VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role_id INTEGER NOT NULL,
    position VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    hire_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE RESTRICT
);

CREATE TABLE room_types (
    room_type_id SERIAL PRIMARY KEY,
    type_name VARCHAR(100) NOT NULL UNIQUE,
    cleaning_standard TEXT,
    frequency VARCHAR(50)
);

CREATE TABLE rooms (
    room_id SERIAL PRIMARY KEY,
    room_number VARCHAR(20) NOT NULL UNIQUE,
    floor INTEGER,
    room_type_id INTEGER NOT NULL,
    description TEXT,
    area NUMERIC(8,2),
    building VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_type_id) REFERENCES room_types(room_type_id)
);

CREATE TABLE task_statuses (
    status_id SERIAL PRIMARY KEY,
    status_name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE TABLE tasks (
    task_id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deadline DATE NOT NULL,
    completed_at TIMESTAMP NULL,
    status_id INTEGER NOT NULL DEFAULT 1,
    room_id INTEGER NOT NULL,
    assigned_to INTEGER NOT NULL,
    created_by INTEGER NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium',
    checklist_required BOOLEAN DEFAULT TRUE,
    photo_required BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (status_id) REFERENCES task_statuses(status_id),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES users(user_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    CONSTRAINT check_priority CHECK (priority IN ('low', 'medium', 'high', 'critical'))
);

CREATE TABLE photo_reports (
    photo_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    photo_type VARCHAR(20) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by INTEGER NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(user_id),
    CONSTRAINT check_photo_type CHECK (photo_type IN ('before', 'after', 'deficiency'))
);

CREATE TABLE checklists (
    checklist_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL UNIQUE,
    comments TEXT,
    is_filled BOOLEAN DEFAULT FALSE,
    filled_at TIMESTAMP NULL,
    filled_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (filled_by) REFERENCES users(user_id)
);

CREATE TABLE checklist_items (
    item_id SERIAL PRIMARY KEY,
    checklist_id INTEGER NOT NULL,
    work_description VARCHAR(255) NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (checklist_id) REFERENCES checklists(checklist_id) ON DELETE CASCADE
);

CREATE TABLE consumables (
    consumable_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    unit VARCHAR(20) NOT NULL,
    current_stock NUMERIC(10,2) DEFAULT 0,
    min_stock NUMERIC(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE used_consumables (
    used_id SERIAL PRIMARY KEY,
    checklist_id INTEGER NOT NULL,
    consumable_id INTEGER NOT NULL,
    quantity NUMERIC(10,2) NOT NULL,
    FOREIGN KEY (checklist_id) REFERENCES checklists(checklist_id) ON DELETE CASCADE,
    FOREIGN KEY (consumable_id) REFERENCES consumables(consumable_id),
    UNIQUE(checklist_id, consumable_id)
);

CREATE TABLE inspections (
    inspection_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    inspector_id INTEGER NOT NULL,
    inspection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    result VARCHAR(20) NOT NULL,
    next_inspection_date TIMESTAMP NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (inspector_id) REFERENCES users(user_id),
    CONSTRAINT check_result CHECK (result IN ('approved', 'rework'))
);

CREATE TABLE comments (
    comment_id SERIAL PRIMARY KEY,
    inspection_id INTEGER NOT NULL,
    comment_text TEXT NOT NULL,
    deficiency_photo VARCHAR(500),
    is_fixed BOOLEAN DEFAULT FALSE,
    fixed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inspection_id) REFERENCES inspections(inspection_id) ON DELETE CASCADE
);

CREATE TABLE reports (
    report_id SERIAL PRIMARY KEY,
    report_type VARCHAR(20) NOT NULL,
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    statistics JSONB,
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    CONSTRAINT check_report_type CHECK (report_type IN ('daily', 'weekly', 'monthly'))
);

CREATE TABLE action_log (
    log_id BIGSERIAL PRIMARY KEY,
    user_id INTEGER,
    action_type VARCHAR(50) NOT NULL,
    table_name VARCHAR(50),
    record_id INTEGER,
    old_data JSONB,
    new_data JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_tasks_status ON tasks(status_id);
CREATE INDEX idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX idx_tasks_deadline ON tasks(deadline);
CREATE INDEX idx_photo_reports_task ON photo_reports(task_id);
CREATE INDEX idx_inspections_task ON inspections(task_id);
CREATE INDEX idx_action_log_user ON action_log(user_id);
