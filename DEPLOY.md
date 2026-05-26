# Загрузка проекта на GitHub

На этом компьютере в командной строке не найден `git`, поэтому самый простой способ без установки программ:

1. Откройте https://github.com/new
2. Название репозитория: `mirea-cleaning-system`
3. Видимость: `Public`
4. Нажмите `Create repository`
5. На странице репозитория нажмите `uploading an existing file`
6. Загрузите содержимое папки `mirea-cleaning-system` или архив `mirea-cleaning-system-github.zip`
7. Нажмите `Commit changes`

## Важно

GitHub хранит код, но сам по себе не запускает Python backend. Чтобы получить публичную рабочую ссылку на сайт, после загрузки на GitHub подключите репозиторий к Render:

1. Откройте https://render.com
2. New -> Web Service
3. Выберите GitHub-репозиторий `mirea-cleaning-system`
4. Render автоматически прочитает `render.yaml`
5. После деплоя появится публичная ссылка вида `https://mirea-cleaning-system.onrender.com`
