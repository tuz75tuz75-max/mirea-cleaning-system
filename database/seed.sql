INSERT INTO roles(role_id, role_name, description) VALUES
(1, 'admin', 'Администратор: управление пользователями, помещениями и справочниками'),
(2, 'supervisor', 'Ответственный за уборку: постановка задач, контроль качества, отчеты'),
(3, 'cleaner', 'Сотрудник клининговой службы: выполнение задач и фотоотчет');

INSERT INTO users(user_id, full_name, login, password_hash, role_id, position, phone, email, hire_date) VALUES
(1, 'Администратор системы', 'admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 1, 'Системный администратор', '+7 495 000-00-01', 'admin@mirea.ru', '2025-09-01'),
(2, 'Ладанова Елена Олеговна', 'supervisor', '02423ab2e61297b8262449c93e19be42fb5bbb275860a7d93b1ebdc7b6535ed7', 2, 'Ответственный за уборку', '+7 495 000-00-02', 'supervisor@mirea.ru', '2025-09-01'),
(3, 'Иванова Мария Сергеевна', 'cleaner', 'c9311ad46bbd488bd393f8a9daffac1ba0bafef7bc5a5d847f197c41fb32692d', 3, 'Сотрудник клининговой службы', '+7 495 000-00-03', 'cleaner1@mirea.ru', '2025-09-10'),
(4, 'Петров Алексей Николаевич', 'cleaner2', 'c9311ad46bbd488bd393f8a9daffac1ba0bafef7bc5a5d847f197c41fb32692d', 3, 'Сотрудник клининговой службы', '+7 495 000-00-04', 'cleaner2@mirea.ru', '2025-09-10');

INSERT INTO room_types(room_type_id, type_name, cleaning_standard, frequency) VALUES
(1, 'Аудитория', 'Сухая и влажная уборка, протирка доски, расстановка мебели', 'ежедневно'),
(2, 'Коридор', 'Влажная уборка пола, удаление мусора, контроль проходных зон', '2 раза в день'),
(3, 'Санузел', 'Дезинфекция сантехники, пополнение расходников, влажная уборка', '3 раза в день'),
(4, 'Кабинет', 'Удаление пыли, влажная уборка пола, вынос мусора', 'ежедневно');

INSERT INTO rooms(room_id, room_number, floor, room_type_id, description, area, building) VALUES
(1, 'А-101', 1, 1, 'Учебная аудитория первого корпуса', 54.30, 'Корпус А'),
(2, 'А-102', 1, 4, 'Кабинет кафедры', 24.70, 'Корпус А'),
(3, 'А-1Х', 1, 3, 'Санузел первого этажа', 18.50, 'Корпус А'),
(4, 'Б-204', 2, 1, 'Лекционная аудитория', 76.00, 'Корпус Б'),
(5, 'Б-2К', 2, 2, 'Коридор второго этажа', 110.20, 'Корпус Б');

INSERT INTO task_statuses(status_id, status_name, description) VALUES
(1, 'created', 'Задание создано и ожидает начала работ'),
(2, 'in_progress', 'Сотрудник приступил к уборке'),
(3, 'on_review', 'Отчет отправлен ответственному на проверку'),
(4, 'completed', 'Уборка проверена и завершена'),
(5, 'rework', 'Задание возвращено на доработку');

INSERT INTO consumables(consumable_id, name, unit, current_stock, min_stock) VALUES
(1, 'Моющее средство универсальное', 'л', 32.5, 8),
(2, 'Дезинфицирующее средство', 'л', 18.0, 6),
(3, 'Пакеты для мусора', 'шт', 240, 60),
(4, 'Бумажные полотенца', 'уп', 42, 12),
(5, 'Жидкое мыло', 'л', 25, 7);

INSERT INTO tasks(task_id, title, description, deadline, completed_at, status_id, room_id, assigned_to, created_by, priority, created_at, updated_at) VALUES
(1, 'Ежедневная уборка аудитории А-101', 'Плановая уборка после учебных занятий', date('now'), NULL, 2, 1, 3, 2, 'high', datetime('now'), datetime('now')),
(2, 'Проверка санузла А-1Х', 'Дезинфекция и пополнение расходных материалов', date('now'), NULL, 3, 3, 4, 2, 'critical', datetime('now'), datetime('now')),
(3, 'Уборка коридора Б-2К', 'Влажная уборка проходной зоны', date('now', '+1 day'), NULL, 1, 5, 3, 2, 'medium', datetime('now'), datetime('now')),
(4, 'Уборка кабинета А-102', 'Удаление пыли и вынос мусора', date('now', '+1 day'), datetime('now', '-1 day'), 4, 2, 4, 2, 'low', datetime('now', '-1 day'), datetime('now'));

INSERT INTO checklists(checklist_id, task_id, comments, is_filled, filled_at, filled_by, created_at) VALUES
(1, 1, NULL, 0, NULL, NULL, datetime('now')),
(2, 2, 'Расходники пополнены, требуется проверка зеркала', 1, datetime('now'), 4, datetime('now')),
(3, 3, NULL, 0, NULL, NULL, datetime('now')),
(4, 4, 'Работа выполнена без замечаний', 1, datetime('now', '-1 day'), 4, datetime('now', '-1 day'));

INSERT INTO checklist_items(checklist_id, work_description, is_completed, sort_order) VALUES
(1, 'Удалить мусор и заменить пакет', 0, 1),
(1, 'Протереть рабочие поверхности', 0, 2),
(1, 'Вымыть пол с учетом типа покрытия', 0, 3),
(1, 'Проверить наличие расходных материалов', 0, 4),
(2, 'Обработать сантехнику дезинфицирующим средством', 1, 1),
(2, 'Пополнить мыло и бумагу', 1, 2),
(2, 'Вымыть пол', 1, 3),
(3, 'Удалить мусор из проходной зоны', 0, 1),
(3, 'Выполнить влажную уборку пола', 0, 2),
(4, 'Удалить пыль с рабочих поверхностей', 1, 1),
(4, 'Вымыть пол', 1, 2),
(4, 'Вынести мусор', 1, 3);

INSERT INTO used_consumables(checklist_id, consumable_id, quantity) VALUES
(2, 2, 0.7),
(2, 4, 1),
(2, 5, 0.5),
(4, 1, 0.3),
(4, 3, 1);

INSERT INTO inspections(task_id, inspector_id, inspection_date, result) VALUES
(4, 2, datetime('now', '-1 day'), 'approved');

INSERT INTO reports(report_id, report_type, date_from, date_to, file_path, created_by, statistics) VALUES
(1, 'daily', date('now', '-1 day'), date('now', '-1 day'), '/api/reports/1/csv', 2, '{}');
