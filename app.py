import base64
import csv
import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cleaning.db"
STATIC_DIR = ROOT / "static"
UPLOAD_DIR = ROOT / "uploads"


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rows(cursor):
    return [dict(row) for row in cursor.fetchall()]


def init_db():
    UPLOAD_DIR.mkdir(exist_ok=True)
    with db() as conn:
        schema = (ROOT / "database" / "schema_sqlite.sql").read_text(encoding="utf-8")
        conn.executescript(schema)
        count = conn.execute("SELECT COUNT(*) AS total FROM roles").fetchone()["total"]
        if count == 0:
            seed = (ROOT / "database" / "seed.sql").read_text(encoding="utf-8")
            conn.executescript(seed)


def audit(conn, user_id, action_type, table_name=None, record_id=None, old_data=None, new_data=None):
    conn.execute(
        """
        INSERT INTO action_log(user_id, action_type, table_name, record_id, old_data, new_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            action_type,
            table_name,
            record_id,
            json.dumps(old_data, ensure_ascii=False) if old_data is not None else None,
            json.dumps(new_data, ensure_ascii=False) if new_data is not None else None,
            now(),
        ),
    )


def parse_id(path, prefix):
    match = re.match(prefix + r"/(\d+)(?:/([a-z_]+))?$", path)
    if not match:
        return None, None
    return int(match.group(1)), match.group(2)


def task_filter_clause(query):
    clauses = []
    params = []
    if query.get("role", [""])[0] == "cleaner" and query.get("user_id"):
        clauses.append("t.assigned_to = ?")
        params.append(int(query["user_id"][0]))
    status = query.get("status", [""])[0]
    if status:
        clauses.append("s.status_name = ?")
        params.append(status)
    search = query.get("search", [""])[0].strip()
    if search:
        clauses.append("(t.title LIKE ? OR r.room_number LIKE ? OR u.full_name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return where, params


def list_tasks(conn, query):
    where, params = task_filter_clause(query)
    return rows(
        conn.execute(
            f"""
            SELECT
                t.task_id, t.title, t.description, t.created_at, t.deadline, t.completed_at,
                t.priority, t.checklist_required, t.photo_required, t.updated_at,
                s.status_name, s.description AS status_description,
                r.room_number, r.floor, r.building, rt.type_name AS room_type,
                u.full_name AS assigned_name, u.user_id AS assigned_to,
                c.full_name AS created_by_name, c.user_id AS created_by,
                (SELECT COUNT(*) FROM photo_reports pr WHERE pr.task_id = t.task_id) AS photo_count,
                (SELECT COUNT(*) FROM inspections i WHERE i.task_id = t.task_id AND i.result = 'rework') AS rework_count,
                (SELECT COUNT(*) FROM checklist_items ci JOIN checklists ch ON ch.checklist_id = ci.checklist_id
                    WHERE ch.task_id = t.task_id AND ci.is_completed = 1) AS completed_items,
                (SELECT COUNT(*) FROM checklist_items ci JOIN checklists ch ON ch.checklist_id = ci.checklist_id
                    WHERE ch.task_id = t.task_id) AS total_items
            FROM tasks t
            JOIN task_statuses s ON s.status_id = t.status_id
            JOIN rooms r ON r.room_id = t.room_id
            JOIN room_types rt ON rt.room_type_id = r.room_type_id
            JOIN users u ON u.user_id = t.assigned_to
            JOIN users c ON c.user_id = t.created_by
            {where}
            ORDER BY
                CASE t.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                t.deadline ASC,
                t.task_id DESC
            """,
            params,
        )
    )


def task_detail(conn, task_id):
    task = conn.execute(
        """
        SELECT t.*, s.status_name, r.room_number, r.floor, r.building, rt.type_name AS room_type,
               u.full_name AS assigned_name, c.full_name AS created_by_name
        FROM tasks t
        JOIN task_statuses s ON s.status_id = t.status_id
        JOIN rooms r ON r.room_id = t.room_id
        JOIN room_types rt ON rt.room_type_id = r.room_type_id
        JOIN users u ON u.user_id = t.assigned_to
        JOIN users c ON c.user_id = t.created_by
        WHERE t.task_id = ?
        """,
        (task_id,),
    ).fetchone()
    if not task:
        return None

    checklist = conn.execute("SELECT * FROM checklists WHERE task_id = ?", (task_id,)).fetchone()
    checklist_id = checklist["checklist_id"] if checklist else None
    return {
        "task": dict(task),
        "checklist": dict(checklist) if checklist else None,
        "items": rows(
            conn.execute(
                "SELECT * FROM checklist_items WHERE checklist_id = ? ORDER BY sort_order, item_id",
                (checklist_id or 0,),
            )
        ),
        "used_consumables": rows(
            conn.execute(
                """
                SELECT uc.*, c.name, c.unit
                FROM used_consumables uc
                JOIN consumables c ON c.consumable_id = uc.consumable_id
                WHERE uc.checklist_id = ?
                ORDER BY c.name
                """,
                (checklist_id or 0,),
            )
        ),
        "photos": rows(conn.execute("SELECT * FROM photo_reports WHERE task_id = ? ORDER BY uploaded_at DESC", (task_id,))),
        "inspections": rows(
            conn.execute(
                """
                SELECT i.*, u.full_name AS inspector_name
                FROM inspections i
                JOIN users u ON u.user_id = i.inspector_id
                WHERE i.task_id = ?
                ORDER BY i.inspection_date DESC
                """,
                (task_id,),
            )
        ),
        "comments": rows(
            conn.execute(
                """
                SELECT cm.*
                FROM comments cm
                JOIN inspections i ON i.inspection_id = cm.inspection_id
                WHERE i.task_id = ?
                ORDER BY cm.created_at DESC
                """,
                (task_id,),
            )
        ),
    }


def bootstrap(conn):
    return {
        "roles": rows(conn.execute("SELECT * FROM roles ORDER BY role_id")),
        "users": rows(
            conn.execute(
                """
                SELECT u.user_id, u.full_name, u.login, u.position, u.phone, u.email,
                       u.is_active, r.role_name
                FROM users u
                JOIN roles r ON r.role_id = u.role_id
                WHERE u.is_active = 1
                ORDER BY r.role_name, u.full_name
                """
            )
        ),
        "rooms": rows(
            conn.execute(
                """
                SELECT r.*, rt.type_name
                FROM rooms r
                JOIN room_types rt ON rt.room_type_id = r.room_type_id
                WHERE r.is_active = 1
                ORDER BY r.building, r.floor, r.room_number
                """
            )
        ),
        "statuses": rows(conn.execute("SELECT * FROM task_statuses ORDER BY status_id")),
        "consumables": rows(conn.execute("SELECT * FROM consumables ORDER BY name")),
    }


def analytics(conn):
    status_counts = rows(
        conn.execute(
            """
            SELECT s.status_name, COUNT(t.task_id) AS total
            FROM task_statuses s
            LEFT JOIN tasks t ON t.status_id = s.status_id
            GROUP BY s.status_id, s.status_name
            ORDER BY s.status_id
            """
        )
    )
    employee_stats = rows(
        conn.execute(
            """
            SELECT u.user_id, u.full_name,
                   COUNT(t.task_id) AS total_tasks,
                   SUM(CASE WHEN s.status_name = 'completed' THEN 1 ELSE 0 END) AS completed_tasks,
                   SUM(CASE WHEN i.result = 'rework' THEN 1 ELSE 0 END) AS reworks
            FROM users u
            JOIN roles r ON r.role_id = u.role_id AND r.role_name = 'cleaner'
            LEFT JOIN tasks t ON t.assigned_to = u.user_id
            LEFT JOIN task_statuses s ON s.status_id = t.status_id
            LEFT JOIN inspections i ON i.task_id = t.task_id
            GROUP BY u.user_id, u.full_name
            ORDER BY completed_tasks DESC, total_tasks DESC
            """
        )
    )
    consumable_stats = rows(
        conn.execute(
            """
            SELECT c.name, c.unit, c.current_stock, c.min_stock,
                   COALESCE(SUM(uc.quantity), 0) AS used_total
            FROM consumables c
            LEFT JOIN used_consumables uc ON uc.consumable_id = c.consumable_id
            GROUP BY c.consumable_id
            ORDER BY used_total DESC, c.name
            """
        )
    )
    totals = conn.execute(
        """
        SELECT
            COUNT(t.task_id) AS tasks_total,
            SUM(CASE WHEN s.status_name = 'completed' THEN 1 ELSE 0 END) AS tasks_completed,
            SUM(CASE WHEN t.deadline < date('now') AND s.status_name != 'completed' THEN 1 ELSE 0 END) AS overdue_tasks
        FROM tasks t
        JOIN task_statuses s ON s.status_id = t.status_id
        """
    ).fetchone()
    return {
        "status_counts": status_counts,
        "employee_stats": employee_stats,
        "consumable_stats": consumable_stats,
        "totals": dict(totals),
    }


def create_report(conn, report_type, user_id):
    today = datetime.now().date()
    date_from = str(today)
    date_to = str(today)
    if report_type == "weekly":
        date_from = str(today.replace(day=max(1, today.day - 6)))
    if report_type == "monthly":
        date_from = str(today.replace(day=1))

    data = analytics(conn)
    report_id = conn.execute(
        """
        INSERT INTO reports(report_type, date_from, date_to, file_path, created_by, statistics, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (report_type, date_from, date_to, "", user_id, json.dumps(data, ensure_ascii=False), now()),
    ).lastrowid
    file_path = f"/api/reports/{report_id}/csv"
    conn.execute("UPDATE reports SET file_path = ? WHERE report_id = ?", (file_path, report_id))
    audit(conn, user_id, "create_report", "reports", report_id, new_data={"report_type": report_type})
    return {
        "report_id": report_id,
        "report_type": report_type,
        "date_from": date_from,
        "date_to": date_to,
        "file_path": file_path,
        "statistics": data,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "MireaCleaning/1.0"

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_static(self, path):
        if path == "/":
            file_path = STATIC_DIR / "index.html"
        elif path.startswith("/static/"):
            file_path = STATIC_DIR / path.replace("/static/", "", 1)
        elif path.startswith("/uploads/"):
            file_path = ROOT / path.lstrip("/")
        else:
            file_path = STATIC_DIR / "index.html"

        try:
            resolved = file_path.resolve()
            if not str(resolved).startswith(str(ROOT)):
                raise FileNotFoundError
            data = resolved.read_bytes()
        except FileNotFoundError:
            self.send_error(404, "File not found")
            return

        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if not path.startswith("/api/"):
            self.send_static(path)
            return

        try:
            with db() as conn:
                if path == "/api/bootstrap":
                    self.send_json(bootstrap(conn))
                elif path == "/api/tasks":
                    self.send_json({"tasks": list_tasks(conn, query)})
                elif path == "/api/analytics":
                    self.send_json(analytics(conn))
                elif path == "/api/audit":
                    self.send_json(
                        {
                            "items": rows(
                                conn.execute(
                                    """
                                    SELECT al.*, u.full_name
                                    FROM action_log al
                                    LEFT JOIN users u ON u.user_id = al.user_id
                                    ORDER BY al.created_at DESC
                                    LIMIT 80
                                    """
                                )
                            )
                        }
                    )
                elif re.match(r"^/api/tasks/\d+$", path):
                    task_id, _ = parse_id(path, r"^/api/tasks")
                    detail = task_detail(conn, task_id)
                    self.send_json(detail if detail else {"error": "Задание не найдено"}, 200 if detail else 404)
                elif re.match(r"^/api/reports/\d+/csv$", path):
                    report_id = int(path.split("/")[3])
                    self.send_report_csv(conn, report_id)
                else:
                    self.send_json({"error": "Маршрут не найден"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            payload = self.read_json()
            with db() as conn:
                if path == "/api/login":
                    self.login(conn, payload)
                elif path == "/api/tasks":
                    self.create_task(conn, payload)
                elif re.match(r"^/api/tasks/\d+/status$", path):
                    self.change_status(conn, int(path.split("/")[3]), payload)
                elif re.match(r"^/api/tasks/\d+/checklist$", path):
                    self.save_checklist(conn, int(path.split("/")[3]), payload)
                elif re.match(r"^/api/tasks/\d+/photos$", path):
                    self.save_photo(conn, int(path.split("/")[3]), payload)
                elif re.match(r"^/api/tasks/\d+/inspection$", path):
                    self.inspect_task(conn, int(path.split("/")[3]), payload)
                elif path == "/api/reports":
                    report = create_report(conn, payload.get("report_type", "daily"), int(payload["user_id"]))
                    self.send_json(report, 201)
                else:
                    self.send_json({"error": "Маршрут не найден"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def login(self, conn, payload):
        user = conn.execute(
            """
            SELECT u.user_id, u.full_name, u.login, u.position, u.email, r.role_name
            FROM users u
            JOIN roles r ON r.role_id = u.role_id
            WHERE u.login = ? AND u.password_hash = ? AND u.is_active = 1
            """,
            (payload.get("login", ""), hash_password(payload.get("password", ""))),
        ).fetchone()
        if not user:
            self.send_json({"error": "Неверный логин или пароль"}, 401)
            return
        audit(conn, user["user_id"], "login", "users", user["user_id"])
        self.send_json({"user": dict(user)})

    def create_task(self, conn, payload):
        task_id = conn.execute(
            """
            INSERT INTO tasks(title, description, deadline, status_id, room_id, assigned_to, created_by,
                              priority, checklist_required, photo_required, created_at, updated_at)
            VALUES (?, ?, ?, (SELECT status_id FROM task_statuses WHERE status_name = 'created'),
                    ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["title"],
                payload.get("description", ""),
                payload["deadline"],
                int(payload["room_id"]),
                int(payload["assigned_to"]),
                int(payload["created_by"]),
                payload.get("priority", "medium"),
                1 if payload.get("checklist_required", True) else 0,
                1 if payload.get("photo_required", True) else 0,
                now(),
                now(),
            ),
        ).lastrowid
        checklist_id = conn.execute(
            "INSERT INTO checklists(task_id, created_at) VALUES (?, ?)",
            (task_id, now()),
        ).lastrowid
        for index, item in enumerate(payload.get("items") or default_checklist(payload.get("room_type", "")), 1):
            conn.execute(
                "INSERT INTO checklist_items(checklist_id, work_description, sort_order) VALUES (?, ?, ?)",
                (checklist_id, item, index),
            )
        audit(conn, int(payload["created_by"]), "create_task", "tasks", task_id, new_data=payload)
        self.send_json(task_detail(conn, task_id), 201)

    def change_status(self, conn, task_id, payload):
        status = payload["status"]
        completed_at = now() if status == "completed" else None
        old = dict(conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone())
        conn.execute(
            """
            UPDATE tasks
            SET status_id = (SELECT status_id FROM task_statuses WHERE status_name = ?),
                completed_at = COALESCE(?, completed_at),
                updated_at = ?
            WHERE task_id = ?
            """,
            (status, completed_at, now(), task_id),
        )
        audit(conn, int(payload["user_id"]), "change_status", "tasks", task_id, old_data=old, new_data={"status": status})
        self.send_json(task_detail(conn, task_id))

    def save_checklist(self, conn, task_id, payload):
        checklist = conn.execute("SELECT * FROM checklists WHERE task_id = ?", (task_id,)).fetchone()
        if not checklist:
            checklist_id = conn.execute(
                "INSERT INTO checklists(task_id, created_at) VALUES (?, ?)",
                (task_id, now()),
            ).lastrowid
        else:
            checklist_id = checklist["checklist_id"]

        conn.execute(
            "UPDATE checklists SET comments = ?, is_filled = 1, filled_at = ?, filled_by = ? WHERE checklist_id = ?",
            (payload.get("comments", ""), now(), int(payload["user_id"]), checklist_id),
        )
        conn.execute("DELETE FROM checklist_items WHERE checklist_id = ?", (checklist_id,))
        for index, item in enumerate(payload.get("items", []), 1):
            conn.execute(
                """
                INSERT INTO checklist_items(checklist_id, work_description, is_completed, sort_order)
                VALUES (?, ?, ?, ?)
                """,
                (checklist_id, item["work_description"], 1 if item.get("is_completed") else 0, index),
            )

        conn.execute("DELETE FROM used_consumables WHERE checklist_id = ?", (checklist_id,))
        for used in payload.get("used_consumables", []):
            quantity = float(used.get("quantity") or 0)
            if quantity <= 0:
                continue
            conn.execute(
                "INSERT INTO used_consumables(checklist_id, consumable_id, quantity) VALUES (?, ?, ?)",
                (checklist_id, int(used["consumable_id"]), quantity),
            )
            conn.execute(
                "UPDATE consumables SET current_stock = MAX(current_stock - ?, 0), updated_at = ? WHERE consumable_id = ?",
                (quantity, now(), int(used["consumable_id"])),
            )

        conn.execute(
            """
            UPDATE tasks
            SET status_id = (SELECT status_id FROM task_statuses WHERE status_name = 'on_review'),
                updated_at = ?
            WHERE task_id = ?
            """,
            (now(), task_id),
        )
        audit(conn, int(payload["user_id"]), "fill_checklist", "checklists", checklist_id, new_data=payload)
        self.send_json(task_detail(conn, task_id))

    def save_photo(self, conn, task_id, payload):
        data_url = payload.get("data_url", "")
        if "," not in data_url:
            raise ValueError("Фото должно передаваться как data URL")
        header, raw = data_url.split(",", 1)
        ext = "png"
        if "jpeg" in header or "jpg" in header:
            ext = "jpg"
        if "webp" in header:
            ext = "webp"
        filename = f"{task_id}_{payload.get('photo_type', 'after')}_{uuid.uuid4().hex}.{ext}"
        destination = UPLOAD_DIR / filename
        destination.write_bytes(base64.b64decode(raw))
        photo_id = conn.execute(
            """
            INSERT INTO photo_reports(task_id, photo_type, file_path, uploaded_at, uploaded_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task_id, payload["photo_type"], f"/uploads/{filename}", now(), int(payload["user_id"])),
        ).lastrowid
        audit(conn, int(payload["user_id"]), "upload_photo", "photo_reports", photo_id, new_data={"photo_type": payload["photo_type"]})
        self.send_json(task_detail(conn, task_id), 201)

    def inspect_task(self, conn, task_id, payload):
        result = payload["result"]
        inspection_id = conn.execute(
            """
            INSERT INTO inspections(task_id, inspector_id, inspection_date, result, next_inspection_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task_id, int(payload["inspector_id"]), now(), result, payload.get("next_inspection_date")),
        ).lastrowid
        comment = payload.get("comment", "").strip()
        if comment:
            conn.execute(
                """
                INSERT INTO comments(inspection_id, comment_text, deficiency_photo, is_fixed, created_at)
                VALUES (?, ?, ?, 0, ?)
                """,
                (inspection_id, comment, payload.get("deficiency_photo"), now()),
            )
        new_status = "completed" if result == "approved" else "rework"
        conn.execute(
            """
            UPDATE tasks
            SET status_id = (SELECT status_id FROM task_statuses WHERE status_name = ?),
                completed_at = CASE WHEN ? = 'completed' THEN ? ELSE completed_at END,
                updated_at = ?
            WHERE task_id = ?
            """,
            (new_status, new_status, now(), now(), task_id),
        )
        audit(conn, int(payload["inspector_id"]), "inspect_task", "inspections", inspection_id, new_data=payload)
        self.send_json(task_detail(conn, task_id), 201)

    def send_report_csv(self, conn, report_id):
        report = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
        if not report:
            self.send_json({"error": "Отчет не найден"}, 404)
            return
        data = json.loads(report["statistics"])
        output = []
        output.append(["Отчет", report["report_type"], report["date_from"], report["date_to"]])
        output.append([])
        output.append(["Статус", "Количество"])
        for item in data["status_counts"]:
            output.append([item["status_name"], item["total"]])
        output.append([])
        output.append(["Сотрудник", "Всего задач", "Завершено", "Возвраты"])
        for item in data["employee_stats"]:
            output.append([item["full_name"], item["total_tasks"], item["completed_tasks"], item["reworks"]])

        text_lines = []
        for row in output:
            text_lines.append(",".join('"' + str(cell).replace('"', '""') + '"' for cell in row))
        body = "\ufeff" + "\n".join(text_lines)
        data_bytes = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="report-{report_id}.csv"')
        self.send_header("Content-Length", str(len(data_bytes)))
        self.end_headers()
        self.wfile.write(data_bytes)

    def log_message(self, fmt, *args):
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))


def default_checklist(room_type):
    base = [
        "Удалить мусор и заменить пакет",
        "Протереть рабочие поверхности",
        "Вымыть пол с учетом типа покрытия",
        "Проверить наличие расходных материалов",
    ]
    if "Санузел" in room_type:
        base.extend(["Обработать сантехнику дезинфицирующим средством", "Пополнить мыло и бумагу"])
    if "Аудитория" in room_type:
        base.extend(["Протереть доску", "Расставить мебель по стандарту"])
    return base


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Система управления уборкой запущена: http://{host}:{port}")
    server.serve_forever()
